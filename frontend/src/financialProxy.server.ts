/** Server entry only. Never import this module from a browser component. */
export async function proxyFinancialData(request: Request): Promise<Response> {
  const headers = { "Cache-Control": "no-store", "Content-Type": "application/json", "X-Content-Type-Options": "nosniff" };
  const error = (status: number, message: string) => Response.json({ error: message }, { status, headers });
  if (request.method !== "GET") return error(405, "Method not allowed");
  const url = new URL(request.url);
  if (url.search) return error(400, "Query parameters are not supported");
  if (request.headers.get("sec-fetch-site") === "cross-site" || (request.headers.get("origin") && request.headers.get("origin") !== url.origin)) return error(403, "Same-origin access required");
  const token = process.env["FINPILOT_API_TOKEN"];
  if (!token) return error(503, "Financial service is not configured");
  try {
    const upstream = new URL(process.env["FINPILOT_BACKEND_URL"] || "http://127.0.0.1:8000");
    if (upstream.username || upstream.password || upstream.search || upstream.hash || upstream.pathname !== "/" || !["http:", "https:"].includes(upstream.protocol)) return error(503, "Financial service is not configured");
    if (upstream.protocol === "http:" && !["127.0.0.1", "localhost", "[::1]"].includes(upstream.hostname)) return error(503, "Financial service requires HTTPS");
    const response = await fetch(new URL("/api/financial-data", upstream), {
      headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
      cache: "no-store", redirect: "error", signal: AbortSignal.timeout(12000),
    });
    if (!response.ok) return error(502, "Financial service request failed");
    // Return only the validated fields needed by this page; omit historical records.
    const { backendFinancialSchema } = await import("./services/backendFinancial");
    const body = await response.json();
    if (!backendFinancialSchema.safeParse(body).success) return error(502, "Invalid financial service response");
    const data = Object.fromEntries(["customer_id", "currency", "as_of_date", "current_balance", "upcoming_transactions", "snapshot_basis", "source_notes"].filter(key => key in body.data).map(key => [key, body.data[key]]));
    data["upcoming_transactions"] = body.data.upcoming_transactions.map((t: Record<string, unknown>) => Object.fromEntries(["id", "date", "description", "amount", "type", "source_status"].map(key => [key, t[key]])));
    return Response.json({ data }, { headers });
  } catch {
    return error(502, "Financial service is unavailable");
  }
}
