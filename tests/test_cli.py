"""AC-1 / AC-8: command line modes and exit codes."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from conftest import EXAMPLES, FIXTURES

from genai_py_codemod.cli import main

GOOD = FIXTURES / "basic_generate" / "before.py"
MANUAL = FIXTURES / "manual_handle_passed" / "before.py"


def project(tmp_path: Path, *sources: Path) -> Path:
    root = tmp_path / "src"
    root.mkdir()
    for index, source in enumerate(sources):
        shutil.copy(source, root / f"mod{index}.py")
    return root


def test_dry_run_prints_diff_and_changes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = project(tmp_path, GOOD)
    before = (root / "mod0.py").read_text()
    assert main([str(root), "--lang", "en"]) == 0
    out = capsys.readouterr().out
    assert "client.models.generate_content(" in out
    assert "-import google.generativeai as genai" in out
    assert "1 file(s) would change" in out
    assert (root / "mod0.py").read_text() == before


def test_examples_first_run(capsys: pytest.CaptureFixture[str]) -> None:
    before = {p: p.read_text() for p in (EXAMPLES / "before").glob("*.py")}
    assert main([str(EXAMPLES / "before"), "--lang", "en"]) == 0
    assert "client.models.generate_content(" in capsys.readouterr().out
    assert {p: p.read_text() for p in before} == before


def test_write_changes_files_and_rerun_changes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = project(tmp_path, GOOD)
    assert main([str(root), "--write", "--lang", "en"]) == 0
    assert "from google import genai" in (root / "mod0.py").read_text()
    capsys.readouterr()
    assert main([str(root), "--write", "--lang", "en"]) == 0
    assert "0 file(s) changed" in capsys.readouterr().out


def test_check_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = project(tmp_path, GOOD)
    assert main([str(root), "--check"]) == 1  # still needs migration
    main([str(root), "--write"])
    assert main([str(root), "--check"]) == 0  # clean
    other = tmp_path / "other"
    other.mkdir()
    manual = project(other, MANUAL)
    assert main([str(manual), "--check", "--lang", "en"]) == 1  # manual spot remains
    assert "handle-escapes" in capsys.readouterr().out


def test_parse_error_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    broken = tmp_path / "broken.py"
    broken.write_text("def f(:\n")
    assert main([str(broken), "--lang", "en"]) == 2
    err = capsys.readouterr().err
    assert "broken.py:1" in err and "cannot parse" in err


def test_usage_errors_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(tmp_path / "missing"), "--lang", "en"]) == 2
    assert "does not exist" in capsys.readouterr().err
    assert main([str(tmp_path), "--lang", "en"]) == 2  # no python files
    assert "no Python files" in capsys.readouterr().err
    assert main([str(tmp_path), "--write", "--check", "--lang", "en"]) == 2
    with pytest.raises(SystemExit) as stop:
        main(["--bogus"])
    assert stop.value.code == 2


def test_json_report_shape(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = project(tmp_path, GOOD, MANUAL)
    assert main([str(root), "--report", "json", "--lang", "en"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["version"] == 1 and report["mode"] == "dry-run"
    assert report["summary"] == {"files": 2, "changed": 1, "manual": 1, "info": 0, "errors": 0}
    by_name = {Path(f["path"]).name: f for f in report["files"]}
    finding = by_name["mod1.py"]["findings"][0]
    assert {"line", "code", "severity"} <= set(finding)
    assert (finding["line"], finding["code"], finding["severity"]) == (14, "handle-escapes", "manual")
    assert by_name["mod0.py"]["changed"] is True and by_name["mod0.py"]["findings"] == []


def test_json_report_check_mode_exit_code(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = project(tmp_path, MANUAL)
    assert main([str(root), "--report", "json", "--check"]) == 1
    assert json.loads(capsys.readouterr().out)["mode"] == "check"


def test_directories_skip_virtualenvs_and_hidden_folders(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    for folder in (".venv", "node_modules", ".git", "pkg"):
        (root / folder).mkdir(parents=True)
        shutil.copy(GOOD, root / folder / "a.py")
    assert main([str(root), "--check"]) == 1
    assert main([str(root / "pkg"), "--write"]) == 0
    assert "generativeai" in (root / ".venv" / "a.py").read_text()  # untouched


def test_files_without_sdk_are_left_alone(tmp_path: Path) -> None:
    plain = tmp_path / "plain.py"
    plain.write_text("print('hello')\n")
    assert main([str(plain), "--check"]) == 0


def test_verify_subcommand_exit_codes(capsys: pytest.CaptureFixture[str]) -> None:
    folder = EXAMPLES / "hand-migrated-bug"
    assert main(["verify", str(folder / "before.py"), str(folder / "after.py"), "--lang", "en"]) == 1
    out = capsys.readouterr().out
    assert "generationConfig.temperature" in out and "safetySettings" in out
    assert "mock transport" in out  # honest about what is checked
    good = FIXTURES / "basic_generate"
    assert main(["verify", str(good / "before.py"), str(good / "expected.py"), "--lang", "en"]) == 0
    out = capsys.readouterr().out
    assert "equivalent (1 requests)" in out and "warning: API version v1beta -> v1" in out
    assert main(["verify", "nope.py", "nope.py", "--lang", "en"]) == 2


def test_verify_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    good = FIXTURES / "basic_generate"
    assert main(["verify", str(good / "before.py"), str(good / "expected.py"), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["equivalent"] is True and data["mock"] is True and data["network_attempts"] == 0


def test_write_keeps_crlf_line_endings(tmp_path: Path) -> None:
    source = (FIXTURES / "basic_generate" / "before.py").read_text().replace("\n", "\r\n") + "# tail\r\n"
    target = tmp_path / "app.py"
    target.write_bytes(source.encode())
    assert main([str(tmp_path), "--write", "--lang", "en"]) == 0
    data = target.read_bytes()
    assert b"client.models.generate_content(" in data
    assert data.count(b"\n") == data.count(b"\r\n") > 0  # no bare LF anywhere
    assert data.endswith(b"# tail\r\n")


def test_write_follows_declared_encoding(tmp_path: Path) -> None:
    source = "# coding: latin-1\n" + (FIXTURES / "basic_generate" / "before.py").read_text() + "# caf\xe9\n"
    target = tmp_path / "app.py"
    target.write_bytes(source.encode("latin-1"))
    assert main([str(tmp_path), "--write", "--lang", "en"]) == 0
    data = target.read_bytes()
    assert b"client.models.generate_content(" in data and data.endswith(b"# caf\xe9\n")


def test_undecodable_file_explains_how_to_fix(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "bad.py").write_bytes(b"x = '\xff\xfe'\n")
    assert main([str(tmp_path), "--lang", "en"]) == 2
    assert "convert it to UTF-8" in capsys.readouterr().err


def test_check_summary_does_not_claim_zero_files_need_migration() -> None:
    from genai_py_codemod.i18n import Translator

    for lang in ("en", "ko"):
        text = Translator(lang)("summary.check", changed=0, manual=1, scanned=1)
        assert "still need migration" not in text and "아직 옮겨야" not in text
