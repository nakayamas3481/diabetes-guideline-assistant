import os
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Optional

import requests


API_BASE = os.getenv("API_BASE", "http://localhost:8000")
TOP_K = int(os.getenv("TOP_K", "5"))

CASES_PATH = os.getenv("CASES_PATH", "eval_cases.jsonl")
OUT_PATH = os.getenv("OUT_PATH", "eval_outputs.jsonl")

# ---- Judge settings ----
ENABLE_JUDGE = os.getenv("ENABLE_JUDGE", "0") == "1"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_JUDGE_MODEL = os.getenv("OPENAI_JUDGE_MODEL", "gpt-5.2")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

# 評価用：カテゴリ0件でも evidence を返す
DEBUG_RETURN_EVIDENCE = os.getenv("DEBUG_RETURN_EVIDENCE", "1") == "1"

# token節約：evidenceテキストは短縮してjudgeに渡す
EVIDENCE_TEXT_MAX = int(os.getenv("EVIDENCE_TEXT_MAX", "700"))
JUDGE_TIMEOUT_SEC = int(os.getenv("JUDGE_TIMEOUT_SEC", "120"))


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    cases = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            cases.append(json.loads(line))
    return cases


def jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = set(a or []), set(b or [])
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def truncate(text: str, max_len: int) -> str:
    if text is None:
        return ""
    t = str(text)
    if len(t) <= max_len:
        return t
    return t[:max_len] + "…"


def query_api(question: str, top_k: int) -> Tuple[bool, Dict[str, Any], str, int]:
    url = f"{API_BASE}/api/query"
    payload = {
        "question": question,
        "top_k": top_k,
        # 評価時のみ：カテゴリ0件でも evidence を返して原因切り分け
        "debug_return_evidence": DEBUG_RETURN_EVIDENCE,
    }
    try:
        r = requests.post(url, json=payload, timeout=120)
    except Exception as e:
        return False, {}, f"request_error: {e}", 0

    if not r.ok:
        return False, {}, r.text, r.status_code

    try:
        return True, r.json(), "", r.status_code
    except Exception as e:
        return False, {}, f"json_parse_error: {e}\nraw={r.text[:5000]}", r.status_code


def call_openai_responses_json_schema(
    api_key: str,
    model: str,
    instructions: str,
    input_text: str,
    schema_name: str,
    schema: Dict[str, Any],
    timeout_sec: int,
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Calls OpenAI Responses API with Structured Outputs (json_schema strict).
    Responses API uses `text.format` (not `response_format`).
    """
    url = f"{OPENAI_BASE_URL}/responses"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    body = {
        "model": model,
        "temperature": 0,
        "instructions": instructions,
        "input": input_text,
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        },
    }

    try:
        r = requests.post(url, headers=headers, json=body, timeout=timeout_sec)
    except Exception as e:
        return False, None, f"judge_request_error: {e}"

    if not r.ok:
        return False, None, f"judge_http_error: {r.status_code}\n{r.text}"

    try:
        data = r.json()
    except Exception as e:
        return False, None, f"judge_json_parse_error: {e}\nraw={r.text[:3000]}"

    # Responses APIは output_text があるのでまずそれを優先
    try:
        out_text = data.get("output_text")
        if isinstance(out_text, str) and out_text.strip():
            parsed = json.loads(out_text)
            return True, parsed, ""
    except Exception:
        pass

    # フォールバック：output 配列から text を集める
    try:
        parts: List[str] = []
        for item in data.get("output", []) or []:
            for c in item.get("content", []) or []:
                if isinstance(c, dict) and "text" in c and isinstance(c["text"], str):
                    parts.append(c["text"])
        joined = "".join(parts).strip()
        if not joined:
            return False, None, f"judge_no_text_output: {json.dumps(data)[:2000]}"
        parsed = json.loads(joined)
        return True, parsed, ""
    except Exception as e:
        return False, None, f"judge_extract_error: {e}\nresp={json.dumps(data)[:3000]}"


def judge_case(
    question: str,
    expected_categories: List[str],
    got_categories: List[str],
    answer: str,
    evidence: List[Dict[str, Any]],
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Returns judge scores as dict:
      retrieval_relevance: 0-5
      groundedness: 0-5
      category_correctness: 0-5
      notes: short text
    """
    if not OPENAI_API_KEY:
        return False, None, "OPENAI_API_KEY is not set"

    # evidenceを短縮して渡す（コスト/速度安定）
    ev_slim = []
    for e in (evidence or []):
        ev_slim.append(
            {
                "source": e.get("source"),
                "page": e.get("page"),
                "score": e.get("score"),
                "text": truncate(e.get("text", ""), EVIDENCE_TEXT_MAX),
            }
        )

    # 0-5採点のJSON Schema
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "retrieval_relevance": {"type": "integer", "minimum": 0, "maximum": 5},
            "groundedness": {"type": "integer", "minimum": 0, "maximum": 5},
            "category_correctness": {"type": "integer", "minimum": 0, "maximum": 5},
            "notes": {"type": "string"},
        },
        "required": ["retrieval_relevance", "groundedness", "category_correctness", "notes"],
    }

    instructions = (
        "You are a strict evaluator for a clinician-facing diabetes guideline RAG system.\n"
        "Score the system output using ONLY the provided evidence.\n"
        "If evidence is empty, retrieval_relevance must be 0.\n"
        "Groundedness measures whether the answer stays within evidence (no unsupported claims).\n"
        "Category correctness measures alignment with expected categories.\n"
        "Return ONLY JSON matching the schema."
    )

    input_text = json.dumps(
        {
            "question": question,
            "expected_categories": expected_categories,
            "model_categories": got_categories,
            "answer": answer,
            "evidence": ev_slim,
            "allowed_categories": [
                "Lifestyle management recommendations",
                "Medication protocol guidance",
                "Complication screening schedules",
                "Referral criteria",
            ],
        },
        ensure_ascii=False,
    )

    return call_openai_responses_json_schema(
        api_key=OPENAI_API_KEY,
        model=OPENAI_JUDGE_MODEL,
        instructions=instructions,
        input_text=input_text,
        schema_name="rag_eval_scores",
        schema=schema,
        timeout_sec=JUDGE_TIMEOUT_SEC,
    )


def main():
    cases = load_jsonl(CASES_PATH)
    print(f"Loaded {len(cases)} cases from {CASES_PATH}")
    print(f"API_BASE={API_BASE} TOP_K={TOP_K}")
    print(f"Writing outputs to {OUT_PATH}")
    print(f"DEBUG_RETURN_EVIDENCE={DEBUG_RETURN_EVIDENCE}")
    print(f"ENABLE_JUDGE={ENABLE_JUDGE} JUDGE_MODEL={OPENAI_JUDGE_MODEL}")

    n_ok = 0
    cat_scores: List[float] = []
    evidence_nonempty = 0

    judge_retr: List[int] = []
    judge_ground: List[int] = []
    judge_cat: List[int] = []

    with open(OUT_PATH, "w", encoding="utf-8") as out:
        for i, c in enumerate(cases, start=1):
            qid = c.get("id", f"row{i:03d}")
            question = c["question"]
            expected = c.get("expected_categories", [])

            ok, data, err, status = query_api(question, TOP_K)
            ts = datetime.now(timezone.utc).isoformat()

            got_categories = []
            got_evidence = []
            answer = ""

            if ok:
                answer = str(data.get("answer", ""))
                got_categories = data.get("categories") or []
                got_evidence = data.get("evidence") or []

            cat_sim = jaccard(expected, got_categories) if ok else 0.0
            has_ev = bool(got_evidence) if ok else False

            judge = None
            judge_error = None
            if ENABLE_JUDGE and ok:
                j_ok, j_data, j_err = judge_case(
                    question=question,
                    expected_categories=expected,
                    got_categories=got_categories,
                    answer=answer,
                    evidence=got_evidence,
                )
                if j_ok and j_data:
                    judge = j_data
                    judge_retr.append(int(j_data["retrieval_relevance"]))
                    judge_ground.append(int(j_data["groundedness"]))
                    judge_cat.append(int(j_data["category_correctness"]))
                else:
                    judge_error = j_err

            row = {
                "id": qid,
                "timestamp_utc": ts,
                "top_k": TOP_K,
                "question": question,
                "expected_categories": expected,
                "ok": ok,
                "http_status": status,
                "error": err if not ok else None,
                "response": data if ok else None,
                "metrics": {
                    "category_jaccard": cat_sim,
                    "evidence_nonempty": has_ev,
                },
                "judge": judge,
                "judge_error": judge_error,
            }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")

            if ok:
                n_ok += 1
                cat_scores.append(cat_sim)
                if has_ev:
                    evidence_nonempty += 1

            # 進捗表示
            msg = f"[{i}/{len(cases)}] {qid} ok={ok} cat_jacc={cat_sim:.2f} evidence={has_ev}"
            if ENABLE_JUDGE and ok:
                if judge:
                    msg += (
                        f" judge(retr={judge['retrieval_relevance']},"
                        f" grd={judge['groundedness']},"
                        f" cat={judge['category_correctness']})"
                    )
                else:
                    msg += " judge=ERR"
            print(msg)

            time.sleep(0.05)

    # 集計
    avg_cat = sum(cat_scores) / len(cat_scores) if cat_scores else 0.0
    ev_rate = evidence_nonempty / n_ok if n_ok else 0.0

    def avg_int(xs: List[int]) -> float:
        return (sum(xs) / len(xs)) if xs else 0.0

    print("\n=== Summary ===")
    print(f"Total cases: {len(cases)}")
    print(f"OK responses: {n_ok}")
    print(f"Avg category jaccard: {avg_cat:.3f}")
    print(f"Evidence non-empty rate: {ev_rate:.3f}")
    if ENABLE_JUDGE:
        print("--- Judge averages (0-5) ---")
        print(f"Avg retrieval_relevance: {avg_int(judge_retr):.2f}")
        print(f"Avg groundedness:       {avg_int(judge_ground):.2f}")
        print(f"Avg category_correctness:{avg_int(judge_cat):.2f}")
    print(f"Outputs: {OUT_PATH}")


if __name__ == "__main__":
    main()