export interface PytestCase {
  name: string;
  status: "passed" | "failed" | "error" | "skipped";
  output?: string;
}

// pytest -v prints one line per test: "path/to/test_file.py::test_name PASSED  [ 50%]"
// (or ::TestClass::test_name for class-based tests). Quiet-mode runs won't match, so an
// empty result here just means "fall back to the raw output" rather than "no tests ran."
const CASE_LINE = /^(\S+::\S+)\s+(PASSED|FAILED|ERROR|SKIPPED)\b/gm;

// pytest -v also emits a "==== FAILURES ====" (and/or "==== ERRORS ====") section after the
// pass/fail line list, with one "____ test_name ____" sub-header per failing test followed by
// its traceback. Both section and sub-header padding are equals-signs/underscores of variable
// width, so we match on the text between them rather than a fixed-width rule.
const SECTION_HEADER = /^=+\s+(.+?)\s+=+$/gm;
const FAILURE_HEADER = /^_{3,}\s+(.+?)\s+_{3,}$/gm;

function collectFailureBlocks(output: string): Map<string, string> {
  const blocks = new Map<string, string>();
  const sectionHeaders = [...output.matchAll(SECTION_HEADER)];
  for (const [index, header] of sectionHeaders.entries()) {
    const title = header[1].trim().toUpperCase();
    if (!title.startsWith("FAILURES") && !title.startsWith("ERRORS")) continue;
    const sectionStart = header.index + header[0].length;
    const sectionEnd = sectionHeaders[index + 1]?.index ?? output.length;
    const sectionText = output.slice(sectionStart, sectionEnd);

    const subHeaders = [...sectionText.matchAll(FAILURE_HEADER)];
    for (const [subIndex, subHeader] of subHeaders.entries()) {
      // Setup/teardown errors are headed "ERROR at setup of test_name" rather than just the name.
      const name = subHeader[1].trim().replace(/^ERROR at (?:setup|teardown) of\s+/i, "");
      const blockStart = subHeader.index + subHeader[0].length;
      const blockEnd = subHeaders[subIndex + 1]?.index ?? sectionText.length;
      blocks.set(name, sectionText.slice(blockStart, blockEnd).trim());
    }
  }
  return blocks;
}

function matchFailureBlock(blocks: Map<string, string>, fullName: string): string | undefined {
  // fullName looks like "path/to/test_file.py::TestClass::test_name[param]"; failure headers
  // use "TestClass.test_name[param]" (dotted) or just "test_name[param]" for module-level tests.
  const segments = fullName.split("::").slice(1);
  if (segments.length === 0) return undefined;
  const methodName = segments[segments.length - 1];
  const dotted = segments.join(".");
  for (const [key, value] of blocks) {
    if (key === dotted || key === methodName || key.startsWith(`${dotted}[`) || key.startsWith(`${methodName}[`)) {
      return value;
    }
  }
  return undefined;
}

export function parsePytestCases(output: string): PytestCase[] {
  const cases: PytestCase[] = [];
  const failureBlocks = collectFailureBlocks(output);
  for (const match of output.matchAll(CASE_LINE)) {
    const [, fullName, status] = match;
    const parts = fullName.split("::");
    const name = parts.length > 1 ? parts.slice(1).join(" › ") : fullName;
    const lowerStatus = status.toLowerCase() as PytestCase["status"];
    const caseOutput = lowerStatus === "failed" || lowerStatus === "error" ? matchFailureBlock(failureBlocks, fullName) : undefined;
    cases.push({ name, status: lowerStatus, output: caseOutput });
  }
  return cases;
}
