import {
  Form,
  useActionData,
  useLoaderData,
  useNavigation,
  useRevalidator,
} from "react-router";
import type { Route } from "../+types/ingest";

type IngestSuccess = {
  pages: number;
  chunks: number;
};

type ActionOk = {
  ok: true;
  data: IngestSuccess;
};

type ActionNg = {
  ok: false;
  status?: number;
  errorText: string;
  errorPretty?: string;
};

type QdrantStatus = {
  mode: string | null;
  qdrant_path: string | null;
  collection: string;
  points_count: number;
  embedding_model: string;
  embedding_dim: number | null;
};

type LoaderOk = {
  ok: true;
  data: QdrantStatus;
};

type LoaderNg = {
  ok: false;
  status?: number;
  errorText: string;
  errorPretty?: string;
};

type LoaderData = LoaderOk | LoaderNg;

export async function clientLoader(_: Route.ClientLoaderArgs) {
  try {
    const res = await fetch("/api/qdrant/status");

    if (!res.ok) {
      const errorText = await res.text();
      let errorPretty: string | undefined;
      try {
        errorPretty = JSON.stringify(JSON.parse(errorText), null, 2);
      } catch {
        // plain text
      }
      return { ok: false, status: res.status, errorText, errorPretty } satisfies LoaderData;
    }

    const data = (await res.json()) as QdrantStatus;
    return { ok: true, data } satisfies LoaderData;
  } catch (e) {
    return {
      ok: false,
      status: 0,
      errorText: e instanceof Error ? e.message : String(e),
    } satisfies LoaderData;
  }
}

export default function IngestPage(_: Route.ComponentProps) {
  const loaderData = useLoaderData() as LoaderData;
  const revalidator = useRevalidator();

  const actionData = useActionData() as ActionOk | ActionNg | undefined;
  const nav = useNavigation();
  const isSubmitting = nav.state === "submitting";

  return (
    <div style={{ display: "grid", gap: 12, maxWidth: 900 }}>
      <h2 style={{ margin: 0 }}>Ingest</h2>

      {/* ★ 既存データ（Qdrant status） */}
      <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12 }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 12,
          }}
        >
          <div style={{ fontWeight: 700 }}>Existing data (Qdrant)</div>

          <button
            type="button"
            onClick={() => revalidator.revalidate()}
            disabled={revalidator.state !== "idle"}
            style={{
              padding: "8px 10px",
              borderRadius: 10,
              border: "1px solid #ddd",
              background: revalidator.state !== "idle" ? "#f3f3f3" : "white",
              cursor: revalidator.state !== "idle" ? "not-allowed" : "pointer",
              fontWeight: 600,
            }}
          >
            {revalidator.state !== "idle" ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {loaderData.ok ? (
          <div style={{ marginTop: 10, display: "grid", gap: 6 }}>
            <div style={{ opacity: 0.85, fontSize: 13 }}>
              mode: <code>{loaderData.data.mode ?? "unknown"}</code>
            </div>
            <div style={{ opacity: 0.85, fontSize: 13 }}>
              path: <code>{loaderData.data.qdrant_path ?? "n/a"}</code>
            </div>
            <div style={{ opacity: 0.85, fontSize: 13 }}>
              collection: <code>{loaderData.data.collection}</code>
            </div>

            <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 4 }}>
              <Stat label="points_count" value={loaderData.data.points_count} />
              <div style={{ opacity: 0.85, fontSize: 13, alignSelf: "center" }}>
                embedding: <code>{loaderData.data.embedding_model}</code>{" "}
                {loaderData.data.embedding_dim != null ? (
                  <>
                    / dim <code>{loaderData.data.embedding_dim}</code>
                  </>
                ) : null}
              </div>
            </div>

            {loaderData.data.points_count === 0 && (
              <div style={{ opacity: 0.7, marginTop: 6 }}>
                No points yet. Run ingest to populate Qdrant.
              </div>
            )}
          </div>
        ) : (
          <pre
            style={{
              margin: "10px 0 0",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              fontSize: 13,
              lineHeight: 1.4,
              color: "crimson",
            }}
          >
            {loaderData.errorPretty ?? loaderData.errorText}
          </pre>
        )}
      </div>

      <Form method="post" style={{ display: "grid", gap: 8 }}>
        <label style={{ display: "grid", gap: 6 }}>
          <span style={{ fontWeight: 600 }}>pdf_path</span>
          <input
            name="pdf_path"
            placeholder="content.pdf"
            required
            autoComplete="off"
            style={{
              padding: "10px 12px",
              border: "1px solid #ddd",
              borderRadius: 8,
              fontSize: 14,
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
          {isSubmitting ? "Ingesting..." : "Ingest"}
        </button>
      </Form>

      {actionData?.ok === true && (
        <div
          style={{
            border: "1px solid #cfe9d4",
            background: "#f2fbf4",
            borderRadius: 12,
            padding: 12,
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Success</div>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <Stat label="pages" value={actionData.data.pages} />
            <Stat label="chunks" value={actionData.data.chunks} />
          </div>
        </div>
      )}

      {actionData?.ok === false && (
        <div
          style={{
            border: "1px solid #f2c7c7",
            background: "#fff5f5",
            borderRadius: 12,
            padding: 12,
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: 8 }}>
            Error {actionData.status ? `(status: ${actionData.status})` : ""}
          </div>
          <pre
            style={{
              margin: 0,
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              fontSize: 13,
              lineHeight: 1.4,
            }}
          >
            {actionData.errorPretty ?? actionData.errorText}
          </pre>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div
      style={{
        border: "1px solid #e6e6e6",
        borderRadius: 10,
        padding: "10px 12px",
        minWidth: 140,
        background: "white",
      }}
    >
      <div style={{ fontSize: 12, opacity: 0.7 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 800 }}>{value}</div>
    </div>
  );
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const form = await request.formData();
  const pdf_path = String(form.get("pdf_path") ?? "").trim();

  if (!pdf_path) {
    return { ok: false, status: 400, errorText: "pdf_path is required" } satisfies ActionNg;
  }

  try {
    const res = await fetch("/api/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pdf_path }),
    });

    if (!res.ok) {
      const errorText = await res.text();
      let errorPretty: string | undefined;
      try {
        errorPretty = JSON.stringify(JSON.parse(errorText), null, 2);
      } catch {
        // plain text
      }
      return { ok: false, status: res.status, errorText, errorPretty } satisfies ActionNg;
    }

    const data = (await res.json()) as IngestSuccess;
    return { ok: true, data } satisfies ActionOk;
  } catch (e) {
    return {
      ok: false,
      status: 0,
      errorText: e instanceof Error ? e.message : String(e),
    } satisfies ActionNg;
  }
}