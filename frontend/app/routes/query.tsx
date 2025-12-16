import { Form } from "react-router";
import type { Route } from "../+types/root";
import { useEffect, useState } from "react";
import { addHistory, type Evidence } from "~/lib/history";

type QueryResponse = {
  answer: string;
  categories: string[];
  evidence: Evidence[];
};

export default function QueryPage(_: Route.ComponentProps) {
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // clientActionの結果を受け取る用（SPAなので sessionStorage で受け渡し）
  useEffect(() => {
    const raw = sessionStorage.getItem("lastQueryResult");
    if (raw) {
      sessionStorage.removeItem("lastQueryResult");
      const parsed = JSON.parse(raw) as { ok: boolean; data?: QueryResponse; error?: string };
      if (parsed.ok && parsed.data) setResult(parsed.data);
      if (!parsed.ok) setError(parsed.error ?? "Unknown error");
    }
  }, []);

  return (
    <div style={{ display: "grid", gap: 12, maxWidth: 900 }}>
      <h2 style={{ margin: 0 }}>Query</h2>

      <Form method="post">
        <div style={{ display: "grid", gap: 8 }}>
          <label>
            Question
            <input name="question" required placeholder="e.g. retinopathy screening frequency" style={{ width: "100%" }} />
          </label>

          <label>
            Top K
            <input name="top_k" type="number" min={1} max={10} defaultValue={5} style={{ width: 120 }} />
          </label>

          <button type="submit">Ask</button>
        </div>
      </Form>

      {error && <div style={{ color: "crimson" }}>{error}</div>}

      {result && (
        <div style={{ border: "1px solid #ddd", padding: 12 }}>
          <div style={{ fontWeight: 700 }}>Answer</div>
          <pre style={{ whiteSpace: "pre-wrap" }}>{result.answer}</pre>

          <div style={{ marginTop: 8 }}>
            <div style={{ fontWeight: 700 }}>Categories</div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {result.categories.map((c) => (
                <span key={c} style={{ border: "1px solid #ccc", padding: "2px 8px", borderRadius: 999 }}>
                  {c}
                </span>
              ))}
              {result.categories.length === 0 && <span style={{ opacity: 0.7 }}>None</span>}
            </div>
          </div>

          <div style={{ marginTop: 12 }}>
            <div style={{ fontWeight: 700 }}>Evidence</div>
            <div style={{ display: "grid", gap: 10 }}>
              {result.evidence.map((e, idx) => (
                <div key={idx} style={{ border: "1px solid #eee", padding: 10 }}>
                  <div style={{ opacity: 0.7, fontSize: 12 }}>
                    page {e.page} / score {e.score.toFixed(3)}
                  </div>
                  <pre style={{ whiteSpace: "pre-wrap" }}>{e.text}</pre>
                </div>
              ))}
              {result.evidence.length === 0 && <div style={{ opacity: 0.7 }}>No evidence</div>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const form = await request.formData();
  const question = String(form.get("question") ?? "");
  const top_k = Number(form.get("top_k") ?? 5);

  try {
    const res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k }),
    });

    if (!res.ok) {
      const txt = await res.text();
      sessionStorage.setItem("lastQueryResult", JSON.stringify({ ok: false, error: txt }));
      return null;
    }

    const data = (await res.json()) as QueryResponse;

    // ★localStorage に保存
    addHistory({
      id: crypto.randomUUID(),
      createdAt: new Date().toISOString(),
      question,
      top_k,
      categories: data.categories ?? [],
      answer: data.answer ?? "",
      evidence: data.evidence ?? [],
    });

    // 画面に結果表示
    sessionStorage.setItem("lastQueryResult", JSON.stringify({ ok: true, data }));
    return null;
  } catch (e: any) {
    sessionStorage.setItem("lastQueryResult", JSON.stringify({ ok: false, error: String(e?.message ?? e) }));
    return null;
  }
}