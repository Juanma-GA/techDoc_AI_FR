import { createServer as createHttpServer } from "node:http";
import { createServer } from "vite";

const port = Number(process.env.E2E_PORT ?? 5173);
const api = createHttpServer((request, response) => {
  request.resume();
  response.writeHead(503, { "Content-Type": "application/json" });
  response.end(JSON.stringify({
    code: "UNMOCKED_E2E_REQUEST", message: "Synthetic API request was not mocked.",
    detail: null, request_id: request.headers["x-request-id"] ?? "",
  }));
});
await new Promise((resolve, reject) => {
  api.once("error", reject);
  api.listen(0, "127.0.0.1", resolve);
});
const address = api.address();
if (!address || typeof address === "string") throw new Error("Missing synthetic API address.");
process.env.VITE_DEV_API_PROXY = `http://127.0.0.1:${address.port}`;
process.env.VITE_API_BASE_URL = "/api/v1";
try {
  const vite = await createServer({ envDir: false, server: { host: "127.0.0.1", port, strictPort: true } });
  await vite.listen();
  const stop = async () => {
    await vite.close();
    api.close(() => process.exit(0));
  };
  process.once("SIGTERM", () => void stop());
  process.once("SIGINT", () => void stop());
  process.stdout.write(`Synthetic-only frontend ready on 127.0.0.1:${port}.\n`);
} catch (error) {
  api.close();
  throw error;
}
