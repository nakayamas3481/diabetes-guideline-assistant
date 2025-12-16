import { useEffect, useState } from "react";
import { clearHistory, loadHistory, removeHistory, type HistoryItem } from "~/lib/history";

export default function HistoryPage() {
  const [items, setItems] = useState<HistoryItem[]>([]);

  const refresh = () => setItems(loadHistory());

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div style={{ display: "grid", gap: 12, maxWidth: 900 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <h2 style={{ margin: 0 }}>History</h2>
        <button
          type="button"
          onClick={() => {
            clearHistory();
            refresh();
          }}
        >
          Clear all
        </button>
      </div>

      {items.length === 0 ? (
        <div style={{ opacity: 0.7 }}>No history yet.</div>
      ) : (
        <div style={{ display: "grid", gap: 10 }}>
          {items.map((it) => (
            <div key={it.id} style={{ border: "1px solid #ddd", padding: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                <div style={{ opacity: 0.7, fontSize: 12 }}>{new Date(it.createdAt).toLocaleString()}</div>
                <button
                  type="button"
                  onClick={() => {
                    removeHistory(it.id);
                    refresh();
                  }}
                >
                  Delete
                </button>
              </div>

              <div style={{ marginTop: 6, fontWeight: 700 }}>{it.question}</div>
              <div style={{ marginTop: 6, opacity: 0.8 }}>categories: {it.categories.join(", ") || "None"}</div>

              <pre style={{ whiteSpace: "pre-wrap", marginTop: 10 }}>{it.answer}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}