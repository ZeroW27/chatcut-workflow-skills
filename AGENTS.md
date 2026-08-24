# Repository instructions

- Skill folder names and `SKILL.md` frontmatter names must match and use lowercase kebab-case.
- Keep every skill package self-contained. Runtime scripts required by a skill stay inside that skill.
- Do not commit real video, audio, `.fcpbundle`, `.fcpxmld`, `.textClipping`, private transcripts, account IDs, or absolute user paths.
- Conversion fixtures must be synthetic and contain no real project or media names.
- The handoff skill is cuts-only: never introduce outer `adjust-transform`, keyframes, or speed changes from ChatCut.
- Preserve original compound resources and refuse to overwrite outputs.
- Before committing, run `python3 tools/validate_repo.py`, `python3 tests/run_tests.py`, and `git diff --check`.
- A successful XML test is not proof of Final Cut Pro import acceptance; report manual acceptance separately.
