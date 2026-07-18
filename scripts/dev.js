const path = require("node:path");
const fs = require("node:fs");
const { concurrently } = require("concurrently");

// Nothing works end-to-end unless all five of these run at once (see README.md's old
// "5 processes, 5 terminals" section) -- this replaces that with one command. Each
// service still has its own npm script (dev:api, dev:gateway, dev:sandbox, dev:worker,
// dev:web) for running just one in isolation, e.g. to debug it with different flags.
const root = path.resolve(__dirname, "..");
const venvPython = path.resolve(
  root,
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python"
);

if (!fs.existsSync(venvPython)) {
  console.error(
    `[dev] No virtualenv Python found at ${venvPython}.\n` +
      "[dev] Create it first -- see docs/setup/SETUP.md section 1."
  );
  process.exit(1);
}

const commands = [
  {
    name: "api",
    prefixColor: "blue",
    command: `"${venvPython}" -m uvicorn app.main:app --app-dir services/api --reload --reload-dir services/api --port 8000`,
  },
  {
    name: "gateway",
    prefixColor: "green",
    command: `"${venvPython}" -m uvicorn llm_gateway.main:app --app-dir services/llm_gateway --port 8010`,
  },
  {
    name: "sandbox",
    prefixColor: "yellow",
    command: `"${venvPython}" -m uvicorn sandbox_runner.main:app --app-dir services/sandbox_runner --port 8020`,
  },
  {
    name: "worker",
    prefixColor: "magenta",
    command: `"${venvPython}" -m worker.main`,
  },
  {
    name: "web",
    prefixColor: "cyan",
    command: "npm run dev:web",
  },
];

const { result } = concurrently(commands, {
  cwd: root,
  killOthersOn: ["failure", "success"],
  prefix: "name",
});

result.then(
  () => process.exit(0),
  () => process.exit(1)
);
