export type Evidence = {
    source?: string; 
    page: number;
    text: string;
    score: number
};

export type HistoryItem = {
  id: string;
  createdAt: string; // ISO
  question: string;
  top_k: number;
  categories: string[];
  answer: string;
  evidence: Evidence[];
};

const KEY = "dga.history.v1";

export function loadHistory(): HistoryItem[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed as HistoryItem[];
  } catch {
    return [];
  }
}

export function saveHistory(items: HistoryItem[]) {
  localStorage.setItem(KEY, JSON.stringify(items));
}

export function addHistory(item: HistoryItem) {
  const items = loadHistory();
  items.unshift(item); // 新しいものを先頭に
  // 50件だけ残す（容量対策）
  saveHistory(items.slice(0, 50));
}

export function clearHistory() {
  localStorage.removeItem(KEY);
}

export function removeHistory(id: string) {
  const items = loadHistory().filter((x) => x.id !== id);
  saveHistory(items);
}