export interface PytestCase {
  name: string;
  status: "passed" | "failed" | "error" | "skipped";
}

// pytest -v prints one line per test: "path/to/test_file.py::test_name PASSED  [ 50%]"
// (or ::TestClass::test_name for class-based tests). Quiet-mode runs won't match, so an
// empty result here just means "fall back to the raw output" rather than "no tests ran."
const CASE_LINE = /^(\S+::\S+)\s+(PASSED|FAILED|ERROR|SKIPPED)\b/gm;

export function parsePytestCases(output: string): PytestCase[] {
  const cases: PytestCase[] = [];
  for (const match of output.matchAll(CASE_LINE)) {
    const [, fullName, status] = match;
    const parts = fullName.split("::");
    const name = parts.length > 1 ? parts.slice(1).join(" › ") : fullName;
    cases.push({ name, status: status.toLowerCase() as PytestCase["status"] });
  }
  return cases;
}
