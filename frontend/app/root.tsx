import { Link, Outlet } from "react-router";

export default function RootLayout() {
  return (
    <div style={{ fontFamily: "system-ui, sans-serif", padding: 16, maxWidth: 960, margin: "0 auto" }}>
      <header style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 16 }}>
        <h1 style={{ margin: 0, fontSize: 20 }}>Diabetes Guideline Assistant</h1>
        <nav style={{ display: "flex", gap: 10, marginLeft: "auto" }}>
          <Link to="/">Query</Link>
          <Link to="/ingest">Ingest</Link>
          <Link to="/history">History</Link>
        </nav>
      </header>

      <main>
        <Outlet />
      </main>
    </div>
  );
}