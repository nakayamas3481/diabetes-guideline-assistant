export type Evidence = {
  source?: string;
  page: number;
  text: string;
  score: number;
};

export type HistoryItem = {
  id: string;
  createdAt: string; // ISO
  question: string;
  top_k?: number;
  categories: string[];
  answer: string;
  evidence: Evidence[];
  evidenceCount?: number;
  expandedSearch?: boolean;
  finalTopK?: number;
  outOfScope?: boolean;
  feedbackThumbs?: "up" | "down";
  feedbackComment?: string;
  feedbackAt?: string;
};

export type FeedbackEntry = {
  id: string;
  historyId?: string;
  question: string;
  answerSnippet: string;
  categories: string[];
  thumbs: "up" | "down";
  comment?: string;
  evidenceCount?: number;
  timestamp: string;
};

const KEY = "dga.history.v1";
const FEEDBACK_KEY = "dga.feedback.v1";

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
  const normalized: HistoryItem = {
    ...item,
    evidenceCount: item.evidenceCount ?? item.evidence?.length ?? 0,
  };
  items.unshift(normalized);
  saveHistory(items.slice(0, 50));
}

export function clearHistory() {
  localStorage.removeItem(KEY);
}

export function removeHistory(id: string) {
  const items = loadHistory().filter((x) => x.id !== id);
  saveHistory(items);
}

export function updateHistoryFeedback(
  id: string | null,
  feedback: {
    thumbs: "up" | "down";
    comment?: string;
    timestamp: string;
    question?: string;
  }
) {
  const items = loadHistory();
  let idx = id ? items.findIndex((x) => x.id === id) : -1;
  if (idx === -1 && feedback.question) {
    idx = items.findIndex((x) => x.question === feedback.question);
  }
  if (idx === -1 && items.length > 0) {
    // as a last resort, update the most recent entry
    idx = 0;
  }
  if (idx === -1) return;
  items[idx] = {
    ...items[idx],
    feedbackThumbs: feedback.thumbs,
    feedbackComment: feedback.comment,
    feedbackAt: feedback.timestamp,
  };
  saveHistory(items);
}

export function loadFeedbackEntries(): FeedbackEntry[] {
  try {
    const raw = localStorage.getItem(FEEDBACK_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed as FeedbackEntry[];
  } catch {
    return [];
  }
}

function saveFeedbackEntries(items: FeedbackEntry[]) {
  localStorage.setItem(FEEDBACK_KEY, JSON.stringify(items));
}

export function recordFeedback(
  entry: Omit<FeedbackEntry, "id" | "timestamp"> & { timestamp?: string }
): FeedbackEntry {
  const list = loadFeedbackEntries();
  const saved: FeedbackEntry = {
    ...entry,
    id: crypto.randomUUID(),
    timestamp: entry.timestamp ?? new Date().toISOString(),
  };
  list.unshift(saved);
  saveFeedbackEntries(list.slice(0, 100));
  return saved;
}

export function latestFeedbackFor(historyId?: string, question?: string): FeedbackEntry | undefined {
  const list = loadFeedbackEntries();
  if (historyId) {
    const found = list.find((f) => f.historyId === historyId);
    if (found) return found;
  }
  if (!question) return undefined;
  return list.find((f) => f.question === question);
}
