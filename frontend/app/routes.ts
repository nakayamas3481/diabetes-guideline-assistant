import { index, route } from "@react-router/dev/routes";

export default [
  index("routes/query.tsx"),
  route("ingest", "routes/ingest.tsx"),
  route("history", "routes/history.tsx"),
];