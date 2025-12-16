from __future__ import annotations

import json
from typing import Any
from openai import OpenAI

CATEGORIES = [
    "Lifestyle management recommendations",
    "Medication protocol guidance",
    "Complication screening schedules",
    "Referral criteria",
]

def _extract_text(resp: Any) -> str:
    t = getattr(resp, "output_text", None)
    if isinstance(t, str) and t.strip():
        return t
    return str(resp)

def classify_categories(
    client: OpenAI,
    model: str,
    question: str,
    evidence: list[dict],
    *,
    score_threshold: float = 0.2,
) -> list[str]:
    """
    Return 0..4 categories aligned with the requirements.

    Strategy:
    - Use QUESTION intent + EVIDENCE support.
    - Only output categories supported by evidence.
    - If out-of-scope OR insufficient evidence -> [].
    """

    if not evidence:
        return []

    # Ensure highest-score first (defensive)
    evidence_sorted = sorted(evidence, key=lambda x: float(x.get("score") or 0.0), reverse=True)

    top_score = float(evidence_sorted[0].get("score") or 0.0)
    if top_score < score_threshold:
        return []

    # Take top N evidence and truncate text to control cost
    top_evs = []
    for e in evidence_sorted[:5]:
        top_evs.append(
            {
                "source": e.get("source"),
                "page": e.get("page"),
                "score": e.get("score"),
                "text": (e.get("text") or "")[:900],
            }
        )

    # --- Structured Outputs schema (json_schema) ---
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "categories": {
                "type": "array",
                "maxItems": 4,
                "items": {"type": "string", "enum": CATEGORIES},
            }
        },
        "required": ["categories"],
    }

    system = (
        "You are a strict classifier for clinician queries about diabetes guideline content.\n"
        "Choose ALL applicable categories from the allowed list, but ONLY if the evidence supports them.\n"
        "If the question is out-of-scope OR evidence is insufficient/irrelevant, return an EMPTY list.\n\n"
        "Allowed categories (exact strings):\n"
        f"{CATEGORIES}\n\n"
        "Category definitions & boundaries:\n"
        "- Lifestyle management recommendations: diet, physical activity, weight loss, smoking/alcohol avoidance, patient education/self-management, foot hygiene/footwear advice.\n"
        "- Medication protocol guidance: medicines (insulin/oral agents/etc), medication adherence, self-monitoring tools/strips/meters, medication-related monitoring practices.\n"
        "- Complication screening schedules: screening/monitoring/exams for complications (eye exam, urine protein/kidney tests, foot/neuropathy assessment) and monitoring schedules (e.g., HbA1c frequency) when discussed as a schedule/assessment.\n"
        "- Referral criteria: referral/back-referral, escalation to specialist assessment or secondary/tertiary care criteria.\n\n"
        "Tie-break rules (important):\n"
        "- If it is primarily about screening/exam frequency or routine assessment -> Complication screening schedules.\n"
        "- If it is primarily about drugs, treatment protocols, or self-monitoring devices/strips -> Medication protocol guidance.\n"
        "- If it mentions referral/back-referral or specialist escalation -> Referral criteria.\n"
        "- If it is about lifestyle counselling/education -> Lifestyle management recommendations.\n\n"
        "Return STRICT JSON only according to the schema."
    )

    user_payload = {
        "question": question,
        "evidence": top_evs,
        "note": "Select categories supported by evidence. If unsupported, return [].",
    }

    try:
        resp = client.responses.create(
            model=model,
            temperature=0,
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": system}]},
                {"role": "user", "content": [{"type": "input_text", "text": json.dumps(user_payload, ensure_ascii=False)}]},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "category_classification",
                    "strict": True,
                    "schema": schema,
                }
            },
        )
    except Exception:
        # If the SDK/environment doesn't accept text.format, fall back to plain response parsing
        resp = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": system}]},
                {"role": "user", "content": [{"type": "input_text", "text": json.dumps(user_payload, ensure_ascii=False)}]},
            ],
        )

    raw = _extract_text(resp).strip()

    try:
        data = json.loads(raw)
        cats = data.get("categories", [])
        if not isinstance(cats, list):
            return []

        allowed = set(CATEGORIES)
        out: list[str] = []
        for c in cats:
            if isinstance(c, str) and c in allowed and c not in out:
                out.append(c)
        return out
    except Exception:
        return []