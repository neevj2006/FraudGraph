import { NextRequest } from "next/server";
export const runtime = "nodejs";
async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (path[0] !== "v1" && path[0] !== "ready" && path[0] !== "health") return new Response("Not found", {status: 404});
  const url = `${process.env.API_URL || "http://127.0.0.1:8000"}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  try {
    let body: Uint8Array | undefined;
    if (request.method === "POST" && request.body) {
      const reader = request.body.getReader();
      const chunks: Uint8Array[] = [];
      let size = 0;
      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > 1024 * 1024) {
          await reader.cancel();
          return Response.json({detail: "Request body too large"}, {status: 413});
        }
        chunks.push(value);
      }
      body = new Uint8Array(size);
      let offset = 0;
      for (const chunk of chunks) {body.set(chunk, offset); offset += chunk.byteLength;}
    }
    const response = await fetch(url, {
      method: request.method, headers: {"Authorization": request.headers.get("authorization") || "", "Content-Type": "application/json"},
      body: body as BodyInit | undefined, cache: "no-store", signal: AbortSignal.timeout(30000)
    });
    const headers: Record<string, string> = {"Content-Type": "application/json", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"};
    if (response.status === 429) headers["Retry-After"] = response.headers.get("retry-after") || "60";
    return new Response(await response.text(), {status: response.status, headers});
  } catch { return Response.json({ detail: "The scoring service is unavailable. Check the API and retry." }, {status: 503}); }
}
export { proxy as GET, proxy as POST };
