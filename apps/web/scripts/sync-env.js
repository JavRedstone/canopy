const fs = require("node:fs");
const path = require("node:path");

const source = path.resolve(__dirname, "../../../.env");
const target = path.resolve(__dirname, "../.env.local");

if (!fs.existsSync(source)) {
  console.warn(`[sync-env] No .env found at ${source}; skipping.`);
  process.exit(0);
}

fs.copyFileSync(source, target);
console.log("[sync-env] Synced repository .env into apps/web/.env.local");
