import { createProductCaptureBackend } from "./product_backend.js";
import type { BridgeRequestV1 } from "./protocol.js";

async function readRequest(): Promise<BridgeRequestV1> {
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) {
    chunks.push(Buffer.from(chunk));
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8")) as BridgeRequestV1;
}

async function main(): Promise<void> {
  const request = await readRequest();
  const response = await createProductCaptureBackend().capture(request);
  process.stdout.write(JSON.stringify(response));
}

main().catch(() => {
  process.stderr.write("Product Pack bridge failed\n");
  process.exitCode = 1;
});
