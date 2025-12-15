# services/category_service.py
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
    - Use question to infer intent
    - Validate categories using evidence (WHO report snippets)
    - If evidence is insufficient/irrelevant -> []
    """

    if not evidence:
        return []

    top_score = float(evidence[0].get("score") or 0.0)
    if top_score < score_threshold:
        return []

    parts = []
    for i, e in enumerate(evidence[:5], start=1):
        parts.append(
            f"[{i}] page={e.get('page')} score={e.get('score')}\n{(e.get('text') or '')[:500]}"
        )
    evidence_text = "\n\n".join(parts)

    system = (
        "You are a classifier for clinician queries about diabetes guideline content.\n"
        "Choose ALL applicable categories from the allowed list, based on the QUESTION.\n"
        "Then validate each chosen category using the EVIDENCE.\n"
        "- Only keep categories that are supported by the evidence.\n"
        "- If the question is out-of-scope or evidence is insufficient, return an EMPTY list.\n\n"
        f"Allowed categories (exact strings): {CATEGORIES}\n"
        "Return STRICT JSON only. No prose.\n"
        "Output format: {\"categories\": [ ... ]}\n"
        "Rules:\n"
        "- categories may be empty\n"
        "- each item must exactly match one allowed category\n"
    )

    user = (
        f"QUESTION:\n{question}\n\n"
        f"EVIDENCE (top retrieved snippets):\n{evidence_text}\n\n"
        "Return JSON only."
    )

    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": [{"type": "input_text", "text": system}]},
            {"role": "user", "content": [{"type": "input_text", "text": user}]},
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