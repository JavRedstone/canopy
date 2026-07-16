const fs = require("node:fs");
const path = require("node:path");

const source = path.resolve(__dirname, "../../../.env");
const target = path.resolve(__dirname, "../.env.local");

if (!fs.existsSync(source)) {
  console.warn(`[sync-env] No .env found at ${source}; skipping.`);
  process.exit(0);
}

// The web app only ever reads NEXT_PUBLIC_* values (see lib/supabase, lib/api.ts). The
// root .env also holds server-only Supabase/OpenAI secrets for services/api and
// services/worker; only the public subset belongs in apps/web, to keep those secrets
// out of a directory that isn't meant to hold them.
const publicLines = fs
  .readFileSync(source, "utf8")
  .split("\n")
  .filter((line) => /^NEXT_PUBLIC_[A-Z0-9_]*=/.test(line));

fs.writeFileSync(target, publicLines.join("\n") + "\n");
console.log(`[sync-env] Synced ${publicLines.length} NEXT_PUBLIC_* value(s) into apps/web/.env.local`);
