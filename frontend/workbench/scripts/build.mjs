import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { build } from "vite";

const workbenchRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const outputRoot = resolve(workbenchRoot, "../../pmqa/web/static");
const assetNames = ["index.html", "assets/app.css", "assets/app.js"];

await build({ configFile: resolve(workbenchRoot, "vite.config.ts") });

const files = {};
for (const name of assetNames) {
  const content = await readFile(resolve(outputRoot, name));
  files[name] = createHash("sha256").update(content).digest("hex");
}
await writeFile(
  resolve(outputRoot, "asset-integrity.json"),
  `${JSON.stringify({ schema_version: "1", files }, null, 2)}\n`,
  { encoding: "utf8" },
);
