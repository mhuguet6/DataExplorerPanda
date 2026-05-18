// Copies backend/outputs/ -> frontend/public/ so the dev server and build
// can serve the charts and insights.json as static assets.
//
// Runs automatically via the `predev` and `prebuild` npm scripts. Re-run
// manually (`npm run sync`) any time you regenerate the backend pipeline.

import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

const backendOutputs = resolve(__dirname, "../../backend/outputs");
const publicDir = resolve(__dirname, "../public");

if (!existsSync(backendOutputs)) {
  console.error(`✖ backend outputs not found at ${backendOutputs}`);
  console.error("  Run `python backend/src/export.py` first.");
  process.exit(1);
}

// Wipe and re-copy to guarantee the public dir matches the backend state
if (existsSync(publicDir)) rmSync(publicDir, { recursive: true, force: true });
mkdirSync(publicDir, { recursive: true });

cpSync(backendOutputs, publicDir, { recursive: true });

console.log(`✓ Synced backend/outputs -> frontend/public`);
