#!/usr/bin/env python3
"""Validate package naming, versions, Python syntax, and basic privacy hygiene."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
PRIVATE_MARKERS = (
    "/Users/",
    "sourceProjectId",
    "Careful Aquamarine",
    "zerozz",
)


def frontmatter(text: str, path: Path) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise ValueError(f"Missing YAML frontmatter: {path}")
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> None:
    errors: list[str] = []
    skill_dirs = sorted(path for path in SKILLS.iterdir() if path.is_dir())
    if not skill_dirs:
        errors.append("No skill packages found")

    for skill_dir in skill_dirs:
        entry = skill_dir / "SKILL.md"
        version_file = skill_dir / "VERSION"
        if not entry.is_file():
            errors.append(f"Missing SKILL.md: {skill_dir}")
            continue
        try:
            metadata = frontmatter(entry.read_text(encoding="utf-8"), entry)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        package_name = metadata.get("name", "")
        if package_name != skill_dir.name:
            errors.append(f"Name mismatch: {skill_dir.name} != {package_name}")
        if not NAME_RE.fullmatch(package_name):
            errors.append(f"Invalid lowercase kebab-case name: {package_name}")
        if not metadata.get("description"):
            errors.append(f"Missing description: {entry}")
        if not version_file.is_file() or not VERSION_RE.fullmatch(
            version_file.read_text(encoding="utf-8").strip()
        ):
            errors.append(f"Missing or invalid VERSION: {skill_dir}")

        for path in skill_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix == ".py":
                try:
                    compile(path.read_text(encoding="utf-8"), str(path), "exec")
                except SyntaxError as exc:
                    errors.append(f"Python syntax error in {path}: {exc}")
            if path.suffix in {".md", ".py", ".txt", ""}:
                text = path.read_text(encoding="utf-8")
                for marker in PRIVATE_MARKERS:
                    if marker in text:
                        errors.append(f"Private marker {marker!r} in {path}")

    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        raise SystemExit(1)
    print(f"validated_skills={len(skill_dirs)}")


if __name__ == "__main__":
    main()
