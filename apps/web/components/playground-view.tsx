"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import Typography from "@mui/material/Typography";
import { LessonRunResult, PlaygroundEnvironmentId, runPlayground } from "@/lib/api";
import { Icon } from "@/components/icon";
import { createClient } from "@/lib/supabase/client";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

const editorOptionsBase = { minimap: { enabled: false }, fontSize: 13, tabSize: 4, scrollBeyondLastLine: false, scrollbar: { alwaysConsumeMouseWheel: false, verticalScrollbarSize: 10, horizontalScrollbarSize: 10 } };

interface EnvironmentConfig {
  label: string;
  monacoLanguage: string;
  framework: string;
  filePath: string;
  defaultContent: string;
}

// Each starter file is a real, runnable passing+failing pair so the demo shows a
// genuine framework-reported failure, not just a script that prints something.
const ENVIRONMENTS: Record<PlaygroundEnvironmentId, EnvironmentConfig> = {
  "python-basic": {
    label: "Python",
    monacoLanguage: "python",
    framework: "pytest",
    filePath: "test_example.py",
    defaultContent: `def add(a, b):\n    return a + b\n\n\ndef test_add_passes():\n    assert add(2, 3) == 5\n\n\ndef test_add_fails():\n    assert add(2, 2) == 5\n`
  },
  "javascript-basic": {
    label: "JavaScript",
    monacoLanguage: "javascript",
    framework: "node --test",
    filePath: "example.test.js",
    defaultContent: `const { test } = require("node:test");\nconst assert = require("node:assert");\n\nfunction add(a, b) {\n  return a + b;\n}\n\ntest("add passes", () => {\n  assert.strictEqual(add(2, 3), 5);\n});\n\ntest("add fails", () => {\n  assert.strictEqual(add(2, 2), 5);\n});\n`
  },
  "go-basic": {
    label: "Go",
    monacoLanguage: "go",
    framework: "go test",
    filePath: "example_test.go",
    defaultContent: `package sandbox\n\nimport "testing"\n\nfunc add(a, b int) int {\n\treturn a + b\n}\n\nfunc TestAddPasses(t *testing.T) {\n\tif add(2, 3) != 5 {\n\t\tt.Fatal("expected 5")\n\t}\n}\n\nfunc TestAddFails(t *testing.T) {\n\tif add(2, 2) != 5 {\n\t\tt.Fatal("expected 5")\n\t}\n}\n`
  },
  "cpp-basic": {
    label: "C++",
    monacoLanguage: "cpp",
    framework: "doctest",
    filePath: "example.cpp",
    defaultContent: `#include "doctest.h"\n\nint add(int a, int b) {\n    return a + b;\n}\n\nTEST_CASE("add passes") {\n    CHECK(add(2, 3) == 5);\n}\n\nTEST_CASE("add fails") {\n    CHECK(add(2, 2) == 5);\n}\n`
  }
};

/** A course-independent sandbox demo: pick a language, edit a real test file, run it
 *  through the same hardened, network-disabled Docker sandbox the coding labs use --
 *  proving multi-language, multi-framework execution without touching the (still
 *  Python-only) AI course-generation pipeline. */
export function PlaygroundView() {
  const [environmentId, setEnvironmentId] = useState<PlaygroundEnvironmentId>("python-basic");
  const [contentByEnvironment, setContentByEnvironment] = useState<Record<PlaygroundEnvironmentId, string>>(
    () => Object.fromEntries(Object.entries(ENVIRONMENTS).map(([id, config]) => [id, config.defaultContent])) as Record<PlaygroundEnvironmentId, string>
  );
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<LessonRunResult>();
  const [error, setError] = useState<string>();

  const config = ENVIRONMENTS[environmentId];
  const content = contentByEnvironment[environmentId];

  async function handleRun() {
    setRunning(true);
    setError(undefined);
    setResult(undefined);
    try {
      const { data } = await createClient().auth.getSession();
      if (!data.session) throw new Error("Your session has expired. Please sign in again.");
      const response = await runPlayground(environmentId, [{ path: config.filePath, content }], data.session.access_token);
      setResult(response);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to run this code.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <Stack sx={{ gap: 2.5 }}>
      <Stack>
        <Typography variant="overline" color="text.secondary">Sandbox playground</Typography>
        <Typography variant="h4" sx={{ letterSpacing: "-0.02em", my: 0.25 }}>Try the sandbox in any supported language</Typography>
        <Typography color="text.secondary">
          The same hardened, network-disabled Docker sandbox that runs coding labs -- not tied to any course, nothing here is saved.
        </Typography>
      </Stack>

      <Tabs value={environmentId} onChange={(_event, value: PlaygroundEnvironmentId) => { setResult(undefined); setError(undefined); setEnvironmentId(value); }}>
        {(Object.keys(ENVIRONMENTS) as PlaygroundEnvironmentId[]).map((id) => (
          <Tab key={id} value={id} label={ENVIRONMENTS[id].label} sx={{ textTransform: "none" }} />
        ))}
      </Tabs>

      <Stack direction="row" sx={{ alignItems: "center", gap: 1 }}>
        <Chip size="small" label={config.framework} />
        <Typography variant="body2" color="text.secondary">{config.filePath}</Typography>
      </Stack>

      <Box sx={{ height: 340, border: 1, borderColor: "divider", borderRadius: 1.5, overflow: "hidden" }}>
        <MonacoEditor
          height="100%"
          language={config.monacoLanguage}
          theme="vs-dark"
          path={config.filePath}
          value={content}
          onChange={(next) => setContentByEnvironment((current) => ({ ...current, [environmentId]: next ?? "" }))}
          options={{ ...editorOptionsBase, automaticLayout: true }}
        />
      </Box>

      <Box>
        <Button variant="contained" startIcon={<Icon name="play_arrow" />} onClick={() => void handleRun()} loading={running}>
          Run {config.framework}
        </Button>
      </Box>

      {error ? <Alert severity="error">{error}</Alert> : null}

      {result ? (
        <Stack sx={{ gap: 1 }}>
          <Alert severity={result.passed ? "success" : "error"}>
            {result.timed_out ? "Timed out" : result.passed ? "All tests passed" : "One or more tests failed"}
          </Alert>
          <Box component="pre" sx={{ m: 0, p: 1.75, overflowX: "auto", border: 1, borderColor: "divider", borderRadius: 1.5, bgcolor: "action.hover", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: "0.85rem", maxHeight: 320, overflowY: "auto" }}>
            {result.output}
          </Box>
        </Stack>
      ) : null}
    </Stack>
  );
}
