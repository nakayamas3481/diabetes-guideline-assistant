import { useEffect, useMemo, useState } from "react";
import {
  clearHistory,
  loadHistory,
  loadFeedbackEntries,
  removeHistory,
  type HistoryItem,
  type FeedbackEntry,
} from "~/lib/history";

function formatDate(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function preview(text: string, max = 240) {
  if (!text) return "";
  if (text.length <= max) return text;
  return text.slice(0, max) + "...";
}

export default function HistoryPage() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [search, setSearch] = useState("");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const mergeFeedback = (history: HistoryItem[], feedback: FeedbackEntry[]): HistoryItem[] => {
    const byId = new Map<string, FeedbackEntry>();
    const byQuestion = new Map<string, FeedbackEntry>();
    for (const f of feedback) {
      if (f.historyId) byId.set(f.historyId, f);
      if (f.question) byQuestion.set(f.question, f);
    }
    return history.map((h) => {
      const hit = (h.id && byId.get(h.id)) || byQuestion.get(h.question);
      if (!hit) return h;
      return {
        ...h,
        feedbackThumbs: hit.thumbs,
        feedbackComment: hit.comment,
        feedbackAt: hit.timestamp,
      };
    });
  };

  const refresh = () => {
    const hist = loadHistory();
    const fb = loadFeedbackEntries();
    setItems(mergeFeedback(hist, fb));
  };

  useEffect(() => {
    refresh();
  }, []);

  const filtered = useMemo(() => {
    const term = search.toLowerCase().trim();
    if (!term) return items;
    return items.filter((it) => it.question.toLowerCase().includes(term));
  }, [items, search]);

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleRerun = (question: string) => {
    sessionStorage.setItem("prefillQuestion", question);
    window.location.href = "/";
  };

  return (
    <div style={{ display: "grid", gap: 12, maxWidth: 960 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>History</h2>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            type="search"
            placeholder="Search questions"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              padding: "8px 10px",
              borderRadius: 8,
              border: "1px solid #ddd",
              minWidth: 220,
            }}
          />
          <button
            type="button"
            onClick={() => {
              clearHistory();
              refresh();
            }}
            style={{
              padding: "8px 12px",
              borderRadius: 8,
              border: "1px solid #ddd",
              background: "white",
              cursor: "pointer",
            }}
          >
            Clear all
          </button>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div style={{ opacity: 0.7 }}>No history yet.</div>
      ) : (
        <div style={{ display: "grid", gap: 12 }}>
          {filtered.map((it) => {
            const categories = it.categories ?? [];
            const evidenceCount = it.evidenceCount ?? it.evidence?.length ?? 0;
            const isExpanded = expandedIds.has(it.id);
            const showOutOfScope = it.outOfScope || categories.length === 0;
            const answerText = it.answer ?? "";

            return (
              <div
                key={it.id}
                style={{
                  border: "1px solid #e6e6e6",
                  borderRadius: 14,
                  padding: 14,
                  background: "white",
                  boxShadow: "0 3px 10px rgba(0,0,0,0.03)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center" }}>
                  <div style={{ fontSize: 12, opacity: 0.7 }}>{formatDate(it.createdAt)}</div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button
                      type="button"
                      onClick={() => handleRerun(it.question)}
                      style={{ border: "1px solid #ddd", borderRadius: 8, padding: "6px 10px", background: "#f9f9f9" }}
                    >
                      Re-run
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        removeHistory(it.id);
                        refresh();
                      }}
                      style={{ border: "1px solid #f2c7c7", borderRadius: 8, padding: "6px 10px", background: "#fff5f5" }}
                    >
                      Delete
                    </button>
                  </div>
                </div>

                <div style={{ marginTop: 8, fontWeight: 800, fontSize: 16, lineHeight: 1.4 }}>{it.question}</div>

                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8, alignItems: "center" }}>
                  {categories.length > 0 ? (
                    categories.map((c) => (
                      <span
                        key={c}
                        style={{
                          border: "1px solid #d6d6d6",
                          borderRadius: 999,
                          padding: "2px 8px",
                          fontSize: 12,
                        }}
                      >
                        {c}
                      </span>
                    ))
                  ) : null}
                  {showOutOfScope && (
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

                <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 8, fontSize: 12, opacity: 0.8 }}>
                  <span>evidence: {evidenceCount}</span>
                  {it.feedbackThumbs && <span>feedback: {it.feedbackThumbs === "up" ? "👍" : "👎"}</span>}
                  {it.feedbackComment && <span>comment: {it.feedbackComment}</span>}
                </div>

                <div style={{ marginTop: 10, border: "1px solid #efefef", borderRadius: 10, padding: 10, background: "#fafafa" }}>
                  <div style={{ fontSize: 13, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
                    {isExpanded ? answerText : preview(answerText)}
                  </div>
                  <button
                    type="button"
                    onClick={() => toggleExpand(it.id)}
                    style={{
                      marginTop: 8,
                      border: "1px solid #ddd",
                      borderRadius: 8,
                      padding: "6px 10px",
                      background: "white",
                      cursor: "pointer",
                    }}
                  >
                    {isExpanded ? "Collapse" : "View details"}
                  </button>
                </div>

                {isExpanded && it.evidence?.length > 0 && (
                  <div style={{ marginTop: 10, display: "grid", gap: 8 }}>
                    <div style={{ fontWeight: 700, fontSize: 13 }}>Evidence</div>
                    {it.evidence.map((ev, idx) => (
                      <details
                        key={idx}
                        style={{
                          border: "1px solid #eee",
                          borderRadius: 10,
                          padding: 10,
                          background: "white",
                        }}
                      >
                        <summary style={{ cursor: "pointer", fontSize: 12, opacity: 0.75 }}>
                          page {ev.page} / score {Number(ev.score ?? 0).toFixed(3)} {ev.source ? `/ ${ev.source}` : ""}
                        </summary>
                        <pre style={{ whiteSpace: "pre-wrap", margin: "8px 0 0" }}>{ev.text}</pre>
                      </details>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
