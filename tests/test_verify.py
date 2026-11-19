"""AC-5 / AC-6: request equivalence checks (real SDK request building, mocked transport, no network)."""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from conftest import EXAMPLES, FIXTURES, fixture_names

from genai_py_codemod import VerifyRunError, verify_files
from genai_py_codemod.verify.compare import Diff, compare_requests, deep_diff, normalize_request

CONVERTIBLE = [
    name
    for name in fixture_names(exclude=("vertex_", "manual_"))
    if not (FIXTURES / name / "no-verify").exists()
]


@pytest.fixture(scope="module")
def results():  # type: ignore[no-untyped-def]
    """Run every convertible fixture once, a few in parallel (each run starts two interpreters)."""

    def run(name: str):  # type: ignore[no-untyped-def]
        folder = FIXTURES / name
        return name, verify_files(folder / "before.py", folder / "expected.py")

    with ThreadPoolExecutor(max_workers=4) as pool:
        return dict(pool.map(run, CONVERTIBLE))


@pytest.mark.parametrize("name", CONVERTIBLE)
def test_equivalent(results, name: str) -> None:  # type: ignore[no-untyped-def]
    result = results[name]
    assert result.equivalent, [d.render() for d in result.diffs]
    assert result.requests_before, "the fixture must send at least one request"
    assert len(result.requests_before) == len(result.requests_after)


@pytest.mark.parametrize("name", CONVERTIBLE)
def test_equivalent_no_network_attempts(results, name: str) -> None:  # type: ignore[no-untyped-def]
    assert results[name].network_attempts == 0


def test_equivalent_version_change_is_only_a_warning(results) -> None:  # type: ignore[no-untyped-def]
    assert results["basic_generate"].warnings == ["API version v1beta -> v1"]
    assert results["latest_alias"].warnings == []  # pinned to v1beta: same version on both sides


def test_equivalent_covers_streaming_chat_embed_and_count_tokens(results) -> None:  # type: ignore[no-untyped-def]
    methods = {r.method for res in results.values() for r in res.requests_after}
    assert {"generateContent", "streamGenerateContent", "countTokens", "batchEmbedContents"} <= methods


def test_hand_migration_mistake_is_found() -> None:
    folder = EXAMPLES / "hand-migrated-bug"
    result = verify_files(folder / "before.py", folder / "after.py")
    assert not result.equivalent
    paths = {d.path for d in result.diffs}
    assert "body.generationConfig.temperature" in paths
    assert "body.safetySettings" in paths
    assert any("generationConfig.temperature" in d.render() and "(missing)" in d.render() for d in result.diffs)


def test_strict_version_turns_the_warning_into_a_failure() -> None:
    folder = FIXTURES / "basic_generate"
    result = verify_files(folder / "before.py", folder / "expected.py", strict_version=True)
    assert not result.equivalent
    assert result.diffs[0].method == "version"


def test_a_file_that_crashes_is_reported_with_the_reason(tmp_path: Path) -> None:
    broken = tmp_path / "broken.py"
    broken.write_text("raise RuntimeError('boom')\n")
    with pytest.raises(VerifyRunError, match="boom"):
        verify_files(broken, broken)


def test_traceback_shows_only_the_script_lines(tmp_path: Path) -> None:
    import runpy

    from genai_py_codemod.verify.runner import is_internal_frame

    # 3.9·3.10 은 runpy 줄을 실제 경로(.../runpy.py)로 찍는다: 접두 "<frozen" 만으로는 못 거른다
    assert is_internal_frame(runpy.__file__)
    assert is_internal_frame("<frozen runpy>")
    assert not is_internal_frame(str(tmp_path / "runpy_helper.py"))

    broken = tmp_path / "exc.py"
    broken.write_text('raise ValueError("bad")\n')
    with pytest.raises(VerifyRunError) as caught:
        verify_files(broken, broken)
    detail = str(caught.value.params)
    assert "exc.py" in detail and "bad" in detail
    assert "runpy" not in detail and "runner.py" not in detail


def _python39() -> str | None:
    import shutil
    import subprocess

    for candidate in ("/usr/bin/python3", shutil.which("python3.9"), shutil.which("python3.10")):
        if not candidate or not Path(candidate).exists():
            continue
        try:
            out = subprocess.run([candidate, "-c", "import sys;print(sys.version_info[:2] < (3, 11))"],
                                 capture_output=True, text=True, timeout=30)
        except OSError:
            continue
        if out.stdout.strip() == "True":
            return candidate
    return None


def test_traceback_on_an_older_interpreter_has_no_runpy_lines(tmp_path: Path) -> None:
    old = _python39()
    if old is None:
        pytest.skip("no Python 3.9/3.10 interpreter on this machine")
    broken = tmp_path / "exc.py"
    broken.write_text('raise ValueError("bad")\n')
    with pytest.raises(VerifyRunError) as caught:
        verify_files(broken, broken, old_python=old)
    detail = str(caught.value.params)
    assert "bad" in detail and "exc.py" in detail
    assert "runpy" not in detail


def test_missing_file_has_a_helpful_message(tmp_path: Path) -> None:
    with pytest.raises(VerifyRunError, match="does not exist"):
        verify_files(tmp_path / "nope.py", tmp_path / "nope.py")


def test_bad_interpreter_has_a_helpful_message(tmp_path: Path) -> None:
    target = tmp_path / "ok.py"
    target.write_text("print('x')\n")
    with pytest.raises(VerifyRunError, match="interpreter not found"):
        verify_files(target, target, old_python=str(tmp_path / "no-python"))


def test_timeout_is_reported(tmp_path: Path) -> None:
    slow = tmp_path / "slow.py"
    slow.write_text("import time\ntime.sleep(30)\n")
    with pytest.raises(VerifyRunError, match="did not finish"):
        verify_files(slow, slow, timeout=1)


def test_network_is_blocked(tmp_path: Path) -> None:
    target = tmp_path / "net.py"
    target.write_text(
        "import socket\n"
        "try:\n    socket.create_connection(('example.com', 80), timeout=1)\n"
        "except OSError:\n    pass\n"
    )
    result = verify_files(target, target)
    assert result.network_attempts == 2  # one attempt per side, both refused


def test_runner_uses_the_given_interpreters(tmp_path: Path) -> None:
    target = tmp_path / "ok.py"
    target.write_text("x = 1\n")
    result = verify_files(target, target, old_python=sys.executable, new_python=sys.executable)
    assert result.nothing_compared and result.requests_before == []


# -- normalization (pure functions) -------------------------------------------------------------------------------
def req(path: str, body: object) -> dict:
    return {"sdk": "x", "method": "POST", "path": path, "query": "", "body": body}


def test_normalize_unifies_old_and_new_shapes() -> None:
    old = normalize_request(
        req(
            "/v1beta/models/gemini-2.5-flash:generateContent",
            {"contents": [{"parts": [{"text": "hi"}], "role": "user"}], "systemInstruction": {"parts": [{"text": "x"}]}},
        )
    )
    new = normalize_request(
        req(
            "/v1/models/gemini-2.5-flash:generateContent",
            {
                "contents": [{"parts": [{"text": "hi"}], "role": "user"}],
                "systemInstruction": {"parts": [{"text": "x"}], "role": "user"},
                "generationConfig": {},
            },
        )
    )
    assert old.body == new.body
    assert (old.version, new.version) == ("v1beta", "v1")
    assert old.model == new.model == "gemini-2.5-flash"


def test_normalize_vertex_path_and_snake_case_keys() -> None:
    normalized = normalize_request(
        req(
            "/v1/projects/p/locations/l/publishers/google/models/gemini-2.5-flash:generateContent",
            {"generation_config": {"max_output_tokens": 5}},
        )
    )
    assert normalized.model == "gemini-2.5-flash"
    assert normalized.body == {"generationConfig": {"maxOutputTokens": 5}}


def test_count_tokens_wrapper_is_unwrapped() -> None:
    old = normalize_request(
        req(
            "/v1beta/models/m:countTokens",
            {"generateContentRequest": {"model": "models/m", "contents": [{"parts": [{"text": "a"}]}], "generationConfig": {}}},
        )
    )
    new = normalize_request(req("/v1/models/m:countTokens", {"contents": [{"parts": [{"text": "a"}], "role": "user"}]}))
    assert old.body == new.body


def test_zero_and_false_values_are_kept() -> None:
    body = normalize_request(req("/v1/models/m:generateContent", {"generationConfig": {"temperature": 0, "x": False}})).body
    assert body == {"generationConfig": {"temperature": 0, "x": False}}


def test_deep_diff_reports_paths() -> None:
    assert deep_diff({"a": {"b": 1}, "c": [1, 2]}, {"a": {"b": 2}, "c": [1]}) == [
        ("body.a.b", 1, 2),
        ("body.c[1]", 2, "(missing)"),
    ]


def test_compare_flags_count_and_model_differences() -> None:
    one = normalize_request(req("/v1/models/a:generateContent", {"contents": []}))
    two = normalize_request(req("/v1/models/b:generateContent", {"contents": []}))
    diffs, _ = compare_requests([one], [two, two])
    assert [d.path for d in diffs] == ["count", "model"]
    assert isinstance(diffs[0], Diff)


def _module_only(tmp_path: Path, body: str, name: str) -> Path:
    path = tmp_path / name
    path.write_text(body)
    return path


def test_zero_requests_on_both_sides_is_not_equivalent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A module that only defines functions sends nothing; that must not be reported as 'same'."""
    from genai_py_codemod.cli import main

    before = _module_only(tmp_path, "import google.generativeai as genai\ndef ask(q):\n    return q\n", "before.py")
    after = _module_only(tmp_path, "def ask(q):\n    return q\n", "after.py")
    result = verify_files(before, after)
    assert result.nothing_compared and not result.equivalent
    assert main(["verify", str(before), str(after), "--lang", "en"]) == 2
    assert "nothing to compare" in capsys.readouterr().out
    assert main(["verify", str(before), str(after), "--lang", "ko"]) == 2
    assert "비교할 요청이 없습니다" in capsys.readouterr().out
    assert main(["verify", str(before), str(after), "--json"]) == 2
    data = __import__("json").loads(capsys.readouterr().out)
    assert data["equivalent"] is False and data["nothing_compared"] is True


def test_missing_sdk_error_says_what_to_install(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from genai_py_codemod.cli import main

    broken = _module_only(tmp_path, "import module_that_does_not_exist_xyz\n", "before.py")
    other = _module_only(tmp_path, "x = 1\n", "after.py")
    with pytest.raises(VerifyRunError) as caught:
        verify_files(broken, other)
    assert caught.value.hint == "old-sdk"
    assert main(["verify", str(broken), str(other), "--lang", "en"]) == 2
    assert "--old-python" in capsys.readouterr().err
    assert main(["verify", str(other), str(broken), "--lang", "ko"]) == 2
    assert "--new-python" in capsys.readouterr().err
