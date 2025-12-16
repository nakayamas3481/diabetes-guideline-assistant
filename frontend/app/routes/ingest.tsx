import { Form, redirect } from "react-router";
import type { Route } from "../+types/ingest";

export default function IngestPage(_: Route.ComponentProps) {
  return (
    <div>
      <h2>Ingest</h2>
      <Form method="post">
        <label>
          pdf_path:
          <input name="pdf_path" placeholder="content.pdf" required />
        </label>
        <button type="submit">Ingest</button>
      </Form>
    </div>
  );
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const form = await request.formData();
  const pdf_path = String(form.get("pdf_path") ?? "");

  const res = await fetch("/api/ingest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pdf_path }),
  });

  if (!res.ok) {
    throw new Error(await res.text());
  }

  return redirect("/");
}