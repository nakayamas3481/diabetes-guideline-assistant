import { Form, useNavigation } from "react-router";
import type { Route } from "../+types/root";
import { useEffect, useMemo, useState } from "react";
import { addHistory, type Evidence } from "~/lib/history";

type QueryResponse = {
  answer: string;
  categories: string[];
  evidence: Evidence[];
};

type StoredResult =
  | { ok: true; data: QueryResponse }
  | { ok: false; error?: string };

function truncate(text: string, max = 280) {
  const t = text ?? "";
  if (t.length <= max) return t;
  return t.slice(0, max) + "…";
}

function prettyIfJson(text: string) {
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

export default function QueryPage(_: Route.ComponentProps) {
  const nav = useNavigation();
  const isSubmitting = nav.state === "submitting";

  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const readFromSession = () => {
    const raw = sessionStorage.getItem("lastQueryResult");
    if (!raw) return;
    sessionStorage.removeItem("lastQueryResult");

    let parsed: StoredResult;
    try {
      parsed = JSON.parse(raw) as StoredResult;
    } catch {
      setError("Failed to parse query result");
      return;
    }

    if (parsed.ok) {
      setError(null);
      setResult(parsed.data);
    } else {
      setResult(null);
      setError(parsed.error ?? "Unknown error");
    }
  };

  // 初回
  useEffect(() => {
    readFromSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 送信完了後にも拾う
  useEffect(() => {
    if (nav.state === "idle") {
      readFromSession();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nav.state]);

  const sortedEvidence = useMemo(() => {
    if (!result?.evidence) return [];
    return [...result.evidence].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  }, [result?.evidence]);

  return (
    <div style={{ display: "grid", gap: 12, maxWidth: 900 }}>
      <h2 style={{ margin: 0 }}>Query</h2>

      <Form method="post" style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12 }}>
        <div style={{ display: "grid", gap: 10 }}>
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontWeight: 600 }}>Question</span>
            <input
              name="question"
              required
              placeholder="e.g. retinopathy screening frequency"
              style={{
                width: "100%",
                boxSizing: "border-box",
                padding: "10px 12px",
                border: "1px solid #ddd",
                borderRadius: 8,
              }}
            />
          </label>

          <label style={{ display: "grid", gap: 6, width: "fit-content" }}>
            <span style={{ fontWeight: 600 }}>Top K</span>
            <input
              name="top_k"
              type="number"
              min={1}
              max={10}
              defaultValue={5}
              style={{
                width: 120,
                boxSizing: "border-box",
                padding: "10px 12px",
                border: "1px solid #ddd",
                borderRadius: 8,
              }}
            />
          </label>

          <button
            type="submit"
            disabled={isSubmitting}
            style={{
              width: "fit-content",
              padding: "10px 14px",
              borderRadius: 10,
              border: "1px solid #ddd",
              background: isSubmitting ? "#f3f3f3" : "white",
              cursor: isSubmitting ? "not-allowed" : "pointer",
              fontWeight: 600,
            }}
          >
            {isSubmitting ? "Asking..." : "Ask"}
          </button>
        </div>
      </Form>

      {error && (
        <div style={{ border: "1px solid #f2c7c7", background: "#fff5f5", borderRadius: 12, padding: 12 }}>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>Error</div>
          <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
            {prettyIfJson(error)}
          </pre>
        </div>
      )}

      {result && (
        <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12 }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Answer</div>
          <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{result.answer}</pre>

          <div style={{ marginTop: 12 }}>
            <div style={{ fontWeight: 700, marginBottom: 6 }}>Categories</div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {result.categories.map((c) => (
                <span
                  key={c}
                  style={{
                    border: "1px solid #ccc",
                    padding: "2px 8px",
                    borderRadius: 999,
                    fontSize: 13,
                  }}
                >
                  {c}
                </span>
              ))}
              {result.categories.length === 0 && <span style={{ opacity: 0.7 }}>None</span>}
            </div>
          </div>

          <div style={{ marginTop: 14 }}>
            <div style={{ fontWeight: 700, marginBottom: 6 }}>Evidence</div>

            {sortedEvidence.length === 0 ? (
              <div style={{ opacity: 0.7 }}>No evidence</div>
            ) : (
              <div style={{ display: "grid", gap: 10 }}>
                {sortedEvidence.map((e, idx) => (
                  <details
                    key={idx}
                    style={{
                      border: "1px solid #eee",
                      borderRadius: 12,
                      padding: 10,
                      background: "white",
                    }}
                  >
                    <summary style={{ cursor: "pointer" }}>
                      <span style={{ opacity: 0.75, fontSize: 12 }}>
                        {e.source ? (
                            <>
                            source <code>{e.source}</code> /{" "}
                            </>
                        ) : null}
                        page {e.page} / score {Number(e.score ?? 0).toFixed(3)}
                        </span>
                    </summary>

                    <pre style={{ whiteSpace: "pre-wrap", marginTop: 10, marginBottom: 0 }}>
                      {e.text}
                    </pre>
                  </details>
                ))}
              </div>
            )}
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