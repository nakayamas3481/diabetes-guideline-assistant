import { Form, useNavigation } from "react-router";
import type { Route } from "../+types/root";
import { useEffect, useMemo, useState } from "react";
import { addHistory, recordFeedback, updateHistoryFeedback, type Evidence } from "~/lib/history";

type QueryResponse = {
  answer: string;
  categories: string[];
  evidence: Evidence[];
};

type StoredResult =
  | {
      ok: true;
      data: QueryResponse;
      finalTopK: number;
      historyId?: string;
      question: string;
      outOfScope?: boolean;
    }
  | { ok: false; error?: string };

const DEFAULT_K = 5;

function truncate(text: string, max = 280) {
  const t = text ?? "";
  if (t.length <= max) return t;
  return t.slice(0, max) + "...";
}

function prettyIfJson(text: string) {
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

function isOutOfScope(data: QueryResponse): boolean {
  const noEvidence = !data.evidence || data.evidence.length === 0;
  const noCategories = !data.categories || data.categories.length === 0;
  return noEvidence || noCategories;
}

export default function QueryPage(_: Route.ComponentProps) {
  const nav = useNavigation();
  const isSubmitting = nav.state === "submitting";

  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [finalTopK, setFinalTopK] = useState(DEFAULT_K);
  const [historyId, setHistoryId] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<string>("");
  const [outOfScope, setOutOfScope] = useState(false);
  const [initialQuestion, setInitialQuestion] = useState<string>("");
  const [feedbackChoice, setFeedbackChoice] = useState<"up" | "down" | null>(null);
  const [feedbackComment, setFeedbackComment] = useState("");
  const [feedbackToast, setFeedbackToast] = useState("");

  const resetFeedbackState = () => {
    setFeedbackChoice(null);
    setFeedbackComment("");
  };

  const applyStoredResult = (parsed: StoredResult & { ok: true }) => {
    setError(null);
    setResult(parsed.data);
    setFinalTopK(parsed.finalTopK ?? DEFAULT_K);
    setHistoryId(parsed.historyId ?? null);
    setCurrentQuestion(parsed.question ?? "");
    setOutOfScope(Boolean(parsed.outOfScope));
    resetFeedbackState();
  };

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
      applyStoredResult(parsed);
    } else {
      setResult(null);
      setError(parsed.error ?? "Unknown error");
    }
  };

  // 初回ロード + rerun遷移からのprefill
  useEffect(() => {
    const prefill = sessionStorage.getItem("prefillQuestion");
    if (prefill) {
      setInitialQuestion(prefill);
      setCurrentQuestion(prefill);
      sessionStorage.removeItem("prefillQuestion");
    }
    readFromSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ナビゲーション完了後にセッション結果を取り込む
  useEffect(() => {
    if (nav.state === "idle") {
      readFromSession();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nav.state]);

  // 新規問い合わせ開始時にフィードバック選択をリセット
  useEffect(() => {
    if (nav.state === "submitting") {
      resetFeedbackState();
    }
  }, [nav.state]);

  const sortedEvidence = useMemo(() => {
    if (!result?.evidence) return [];
    return [...result.evidence].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  }, [result?.evidence]);

  const evidenceCount = result?.evidence?.length ?? 0;

  // New result -> reset feedback selection
  useEffect(() => {
    resetFeedbackState();
  }, [historyId]);

  useEffect(() => {
    resetFeedbackState();
  }, [result?.answer, result?.categories, result?.evidence]);

  const handleRecordFeedback = (thumbs: "up" | "down") => {
    if (!result) return;
    const entry = recordFeedback({
      historyId: historyId ?? undefined,
      question: currentQuestion,
      answerSnippet: truncate(result.answer, 600),
      categories: result.categories ?? [],
      thumbs,
      comment: feedbackComment || undefined,
      evidenceCount,
    });
    updateHistoryFeedback(historyId, {
      thumbs: entry.thumbs,
      comment: entry.comment,
      timestamp: entry.timestamp,
      question: currentQuestion,
    });
    setFeedbackToast("Feedback recorded");
    setTimeout(() => setFeedbackToast(""), 2200);
  };

  return (
    <div style={{ display: "grid", gap: 12, maxWidth: 900 }}>
      <h2 style={{ margin: 0 }}>Query</h2>

      <Form
        method="post"
        style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12 }}
        onSubmit={() => resetFeedbackState()}
      >
        <div style={{ display: "grid", gap: 10 }}>
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontWeight: 600 }}>Question</span>
            <input
              name="question"
              required
              defaultValue={initialQuestion}
              placeholder="e.g. retinopathy screening frequency"
              style={{
                width: "100%",
                boxSizing: "border-box",
                padding: "10px 12px",
                border: "1px solid #ddd",
                borderRadius: 8,
              }}
              onChange={(e) => setCurrentQuestion(e.target.value)}
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
        <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12, display: "grid", gap: 10 }}>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <div style={{ fontWeight: 700 }}>Answer</div>
            <div style={{ fontSize: 12, opacity: 0.7 }}>top_k={finalTopK}</div>
            {outOfScope && (
              <span
                style={{
                  border: "1px solid #f0c2c2",
                  background: "#fff5f5",
                  borderRadius: 999,
                  padding: "2px 8px",
                  fontSize: 12,
                }}
              >
                Out of scope
              </span>
            )}
          </div>

          <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{result.answer}</pre>

          <div>
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

          <div>
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

          <div
            key={historyId ?? currentQuestion ?? "feedback"}
            style={{ borderTop: "1px solid #eee", paddingTop: 10, display: "grid", gap: 8 }}
          >
            <div style={{ fontWeight: 700 }}>Feedback</div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <button
                type="button"
                onClick={() => {
                  setFeedbackChoice("up");
                  setFeedbackReason("");
                  setFeedbackComment("");
                  handleRecordFeedback("up");
                }}
                style={{
                  padding: "6px 10px",
                  borderRadius: 8,
                  border: feedbackChoice === "up" ? "2px solid #0b6b31" : "1px solid #ccc",
                  background: feedbackChoice === "up" ? "#f2fbf4" : "white",
                  cursor: "pointer",
                }}
              >
                👍
              </button>
              <button
                type="button"
                onClick={() => {
                  setFeedbackChoice("down");
                }}
                style={{
                  padding: "6px 10px",
                  borderRadius: 8,
                  border: feedbackChoice === "down" ? "2px solid #b5563b" : "1px solid #ccc",
                  background: feedbackChoice === "down" ? "#fff4f0" : "white",
                  cursor: "pointer",
                }}
              >
                👎
              </button>
              {feedbackToast && <span style={{ fontSize: 12, color: "#0b6b31" }}>{feedbackToast}</span>}
            </div>

            {feedbackChoice === "down" && (
              <div
                style={{
                  display: "grid",
                  gap: 8,
                  maxWidth: 520,
                  padding: 10,
                  border: "1px solid #f2c7c7",
                  borderRadius: 10,
                  background: "#fff5f5",
                }}
              >
                <label style={{ display: "grid", gap: 6 }}>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>Comment (optional)</span>
                  <textarea
                    value={feedbackComment}
                    onChange={(e) => setFeedbackComment(e.target.value)}
                    rows={3}
                    style={{ padding: 10, borderRadius: 8, border: "1px solid #e0bcbc", resize: "vertical" }}
                  />
                </label>
                <button
                  type="button"
                  onClick={() => feedbackChoice === "down" && handleRecordFeedback("down")}
                  style={{
                    width: "fit-content",
                    padding: "8px 12px",
                    borderRadius: 8,
                    border: "1px solid #b5563b",
                    background: "#fff",
                    cursor: "pointer",
                    fontWeight: 600,
                  }}
                >
                  Save feedback
                </button>
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
  const question = String(form.get("question") ?? "").trim();
  if (!question) {
    sessionStorage.setItem("lastQueryResult", JSON.stringify({ ok: false, error: "Question is required" }));
    return null;
  }

  try {
    const res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k: DEFAULT_K, debug_return_evidence: true }),
    });
    if (!res.ok) {
      const txt = await res.text();
      sessionStorage.setItem("lastQueryResult", JSON.stringify({ ok: false, error: txt }));
      return null;
    }

    const data = (await res.json()) as QueryResponse;
    const historyId = crypto.randomUUID();
    const outOfScope = isOutOfScope(data);

    addHistory({
      id: historyId,
      createdAt: new Date().toISOString(),
      question,
      top_k: DEFAULT_K,
      categories: data.categories ?? [],
      answer: data.answer ?? "",
      evidence: data.evidence ?? [],
      evidenceCount: data.evidence?.length ?? 0,
      outOfScope,
    });

    sessionStorage.setItem(
      "lastQueryResult",
      JSON.stringify({
        ok: true,
        data,
        finalTopK: DEFAULT_K,
        historyId,
        question,
        outOfScope,
      })
    );
    return null;
  } catch (e: any) {
    sessionStorage.setItem("lastQueryResult", JSON.stringify({ ok: false, error: String(e?.message ?? e) }));
    return null;
  }
}
