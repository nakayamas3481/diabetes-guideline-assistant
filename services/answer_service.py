from openai import OpenAI

SYSTEM_PROMPT = """You are a clinical guideline assistant.
Answer ONLY using the provided evidence. If evidence is insufficient, say so.
Keep the answer concise and cite page numbers from evidence when possible.
"""

def build_context(evidence: list[dict]) -> str:
    lines = []
    for e in evidence:
        page = e.get("page", "?")
        text = (e.get("text") or "").replace("\n", " ").strip()
        lines.append(f"[p{page}] {text}")
    return "\n".join(lines)

def generate_answer(
    client: OpenAI,
    model: str,
    question: str,
    evidence: list[dict],
) -> str:
    context = build_context(evidence)
    user_prompt = f"""Question:
{question}

Evidence:
{context}

Write an answer based on the evidence above."""

    resp = client.responses.create(
        model=model,
        instructions=SYSTEM_PROMPT,
        input=user_prompt,
    )

    return (resp.output_text or "").strip()