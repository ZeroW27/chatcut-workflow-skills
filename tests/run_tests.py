#!/usr/bin/env python3
"""Run synthetic end-to-end checks for every packaged converter route."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
SKILL = ROOT / "skills" / "chatcut-final-cut-compound-handoff"
SCRIPTS = SKILL / "scripts"


def run(*args: str) -> str:
    completed = subprocess.run(
        [sys.executable, *args],
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout


def assert_cuts_only(path: Path) -> None:
    payload = path / "Info.fcpxml" if path.is_dir() else path
    root = ET.parse(payload).getroot()
    projects = root.findall("./project") + root.findall("./library/event/project")
    project = projects[-1]
    spine = project.find("./sequence/spine")
    assert spine is not None
    assert len(list(spine)) == 2
    assert not spine.findall("./*/adjust-transform")
    assert not spine.findall("./*/timeMap")


def main() -> None:
    chatcut = FIXTURES / "chatcut-cuts.xml"
    compound = FIXTURES / "final-cut-compound.fcpxml"
    inline_sync = FIXTURES / "final-cut-inline-sync.fcpxmld"

    with tempfile.TemporaryDirectory(prefix="chatcut-workflow-skills-") as raw:
        temp = Path(raw)

        compound_output = temp / "compound-output.fcpxmld"
        report = run(
            str(SCRIPTS / "apply_chatcut_to_compound_fcpxml.py"),
            "--chatcut", str(chatcut),
            "--fcpxml-source", str(compound),
            "--output", str(compound_output),
            "--name", "Synthetic Compound Output",
            "--cuts-only",
        )
        assert "ignored_visual_clips=1" in report
        run(
            str(SCRIPTS / "validate_fcpxml_handoff.py"),
            "--input", str(compound_output),
            "--expect-cuts-only",
        )
        assert_cuts_only(compound_output)

        sync_output = temp / "sync-output.fcpxmld"
        run(
            str(SCRIPTS / "sync_chatcut_into_fcpxmld.py"),
            "--chatcut", str(chatcut),
            "--fcpxmld", str(inline_sync),
            "--output", str(sync_output),
            "--project", "Synthetic Sync Project",
            "--name", "Synthetic Sync Output",
            "--cuts-only",
        )
        run(
            str(SCRIPTS / "validate_fcpxml_handoff.py"),
            "--input", str(sync_output),
            "--project", "Synthetic Sync Output",
            "--expect-cuts-only",
        )
        assert_cuts_only(sync_output)

        standalone_output = temp / "standalone.fcpxml"
        run(
            str(SCRIPTS / "convert_xmeml_to_fcpxml.py"),
            str(chatcut), str(standalone_output),
            "--source", "/synthetic/Synthetic.mov",
            "--cuts-only",
        )
        run(
            str(SCRIPTS / "validate_fcpxml_handoff.py"),
            "--input", str(standalone_output),
            "--expect-cuts-only",
        )
        assert_cuts_only(standalone_output)

    print("converter_routes=3")


if __name__ == "__main__":
    main()
