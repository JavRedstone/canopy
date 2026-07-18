import json
from types import SimpleNamespace

from worker.lesson_agent import repair_bundle, strip_starter_solution
from worker.sandbox import SandboxRunResult


def _call(name: str, call_id: str, **arguments: object) -> SimpleNamespace:
    return SimpleNamespace(type="function_call", name=name, call_id=call_id, arguments=json.dumps(arguments))


class FakeResponses:
    def __init__(self, outputs: list[list[SimpleNamespace]]) -> None:
        self._outputs = list(outputs)
        self.call_count = 0

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.call_count += 1
        output = self._outputs.pop(0) if self._outputs else []
        return SimpleNamespace(output=output)


class FakeSandbox:
    def __init__(self, results: list[SandboxRunResult]) -> None:
        self._results = list(results)
        self.runs: list[dict[str, str]] = []

    def run_pytest(self, files: list) -> SandboxRunResult:
        snapshot = {f.path: f.content for f in files}
        self.runs.append(snapshot)
        return self._results.pop(0) if self._results else SandboxRunResult(exit_code=1, output="no more results", timed_out=False)


FAILING = SandboxRunResult(exit_code=1, output="1 failed", timed_out=False)
PASSING = SandboxRunResult(exit_code=0, output="1 passed", timed_out=False)


def test_loop_exits_once_model_stops_calling_tools() -> None:
    responses = FakeResponses(
        outputs=[
            [_call("write_file", "c1", path="solution.py", content="def f(): return 1\n")],
            [],  # model emits no more tool calls -> loop breaks
        ]
    )
    sandbox = FakeSandbox(results=[PASSING])  # only the final re-verification run
    files = {"solution.py": "def f(): return 0\n", "test_solution.py": "..."}

    final_files, result = repair_bundle(
        openai_client=SimpleNamespace(responses=responses),
        model="test-model",
        sandbox=sandbox,
        files=files,
        writable_paths={"solution.py"},
        failing_result=FAILING,
        max_tool_turns=5,
    )

    assert responses.call_count == 2
    assert final_files["solution.py"] == "def f(): return 1\n"
    assert result is PASSING


def test_write_file_mutation_is_visible_to_a_later_run_tests() -> None:
    responses = FakeResponses(
        outputs=[
            [
                _call("write_file", "c1", path="solution.py", content="def f(): return 42\n"),
                _call("run_tests", "c2"),
            ],
            [],
        ]
    )
    sandbox = FakeSandbox(results=[FAILING, PASSING])
    files = {"solution.py": "def f(): return 0\n"}

    repair_bundle(
        openai_client=SimpleNamespace(responses=responses),
        model="test-model",
        sandbox=sandbox,
        files=files,
        writable_paths={"solution.py"},
        failing_result=FAILING,
        max_tool_turns=5,
    )

    # the in-loop run_tests call must see the write_file mutation from the same turn
    assert sandbox.runs[0]["solution.py"] == "def f(): return 42\n"


def test_loop_is_capped_at_max_tool_turns() -> None:
    infinite_calls = [[_call("read_file", "c1", path="solution.py")] for _ in range(100)]
    responses = FakeResponses(outputs=infinite_calls)
    sandbox = FakeSandbox(results=[FAILING])
    files = {"solution.py": "x = 1\n"}

    repair_bundle(
        openai_client=SimpleNamespace(responses=responses),
        model="test-model",
        sandbox=sandbox,
        files=files,
        writable_paths={"solution.py"},
        failing_result=FAILING,
        max_tool_turns=3,
    )

    assert responses.call_count == 3


def test_result_always_comes_from_sandbox_never_inferred_from_model_text() -> None:
    # Model calls run_tests and gets a FAILING result mid-loop, then stops calling tools.
    # The function must still return the sandbox's own final re-verification run, not the
    # mid-loop result and not anything inferred from the model's (absent) text claim.
    responses = FakeResponses(
        outputs=[
            [_call("run_tests", "c1")],
            [],
        ]
    )
    sandbox = FakeSandbox(results=[FAILING, PASSING])
    files = {"solution.py": "x = 1\n"}

    _, result = repair_bundle(
        openai_client=SimpleNamespace(responses=responses),
        model="test-model",
        sandbox=sandbox,
        files=files,
        writable_paths={"solution.py"},
        failing_result=FAILING,
        max_tool_turns=5,
    )

    assert len(sandbox.runs) == 2  # the mid-loop run_tests call, plus the final re-verification
    assert result is PASSING


def test_write_file_outside_writable_paths_is_rejected_not_applied() -> None:
    # The model tries to "fix" a failing reference solution by rewriting the hidden test
    # instead -- this must be rejected, not silently written, so a lesson can never ship
    # "validated" with a test that was weakened to make a wrong solution pass.
    responses = FakeResponses(
        outputs=[
            [_call("write_file", "c1", path="test_solution.py", content="def test_it():\n    assert True\n")],
            [_call("write_file", "c2", path="solution.py", content="def f(): return 1\n")],
            [],
        ]
    )
    sandbox = FakeSandbox(results=[PASSING])
    files = {"solution.py": "def f(): return 0\n", "test_solution.py": "def test_it():\n    assert f() == 1\n"}

    final_files, _ = repair_bundle(
        openai_client=SimpleNamespace(responses=responses),
        model="test-model",
        sandbox=sandbox,
        files=files,
        writable_paths={"solution.py"},
        failing_result=FAILING,
        max_tool_turns=5,
    )

    assert final_files["test_solution.py"] == "def test_it():\n    assert f() == 1\n"  # unchanged
    assert final_files["solution.py"] == "def f(): return 1\n"  # the legitimate write still applied


def test_strip_starter_solution_removes_the_working_implementation() -> None:
    responses = FakeResponses(
        outputs=[
            [_call("write_file", "c1", path="solution.py", content="def f():\n    ...\n")],
            [],
        ]
    )
    sandbox = FakeSandbox(results=[FAILING])  # stub now correctly fails
    files = {"solution.py": "def f(): return 1\n", "test_solution.py": "def test_it():\n    assert f() == 1\n"}

    final_files, result = strip_starter_solution(
        openai_client=SimpleNamespace(responses=responses),
        model="test-model",
        sandbox=sandbox,
        files=files,
        writable_paths={"solution.py"},
        passing_result=PASSING,
        max_tool_turns=5,
    )

    assert final_files["solution.py"] == "def f():\n    ...\n"
    assert result is FAILING


def test_strip_starter_solution_cannot_write_a_test_file() -> None:
    responses = FakeResponses(
        outputs=[
            [_call("write_file", "c1", path="test_solution.py", content="def test_it():\n    pass\n")],
            [],
        ]
    )
    sandbox = FakeSandbox(results=[PASSING])  # nothing legitimate changed, so it still passes
    files = {"solution.py": "def f(): return 1\n", "test_solution.py": "def test_it():\n    assert f() == 1\n"}

    final_files, result = strip_starter_solution(
        openai_client=SimpleNamespace(responses=responses),
        model="test-model",
        sandbox=sandbox,
        files=files,
        writable_paths={"solution.py"},
        passing_result=PASSING,
        max_tool_turns=5,
    )

    assert final_files["test_solution.py"] == "def test_it():\n    assert f() == 1\n"  # unchanged
    assert result is PASSING
