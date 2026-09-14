# ChatCut Workflow Skills

Reusable workflow skills for a two-stage talking-head editing pipeline:

1. `chatcut-a-roll-hard-cut` makes a content-only A-roll hard cut in ChatCut from a transcript or outline.
2. `chatcut-final-cut-compound-handoff` transfers an approved ChatCut cut list into a new Final Cut Pro FCPXML/FCPXMLD while preserving the original compound-clip media structure.

Both skills intentionally separate editorial decisions from finishing. The first skill does not export XML; the second does not reinterpret the spoken content or transfer ChatCut visual motion.

## Repository layout

```text
skills/
  chatcut-a-roll-hard-cut/
  chatcut-final-cut-compound-handoff/
tests/
  fixtures/
  run_tests.py
tools/
  validate_repo.py
```

Each skill folder is a self-contained package whose directory name matches the `name` in `SKILL.md`.

## Development

Run the complete local check from the repository root:

```bash
PYTHONPYCACHEPREFIX=/tmp/chatcut-workflow-skills-pycache python3 tools/validate_repo.py
PYTHONPYCACHEPREFIX=/tmp/chatcut-workflow-skills-pycache python3 tests/run_tests.py
git diff --check
```

Tests use synthetic XML only. Never commit real media, private transcripts, Final Cut libraries, project exports, account IDs, or absolute user paths.

## Versioning

The two skills version independently using Semantic Versioning. Each package has a `VERSION` file.

- Patch: a compatible correction to instructions, validation, or conversion behavior.
- Minor: a backward-compatible input mode or capability.
- Major: a breaking change to required inputs, editing policy, or output semantics.

Release tags are scoped by skill:

```text
chatcut-a-roll-hard-cut-v0.1.0
chatcut-final-cut-compound-handoff-v0.1.0
```

Treat Git as the development source of truth. Update the existing saved ChatCut Workflow Skill from a reviewed tag instead of creating duplicate skills for each revision.

## Status

Both packages start at `0.1.0`. Static and synthetic conversion checks pass; real Final Cut Pro import remains a manual acceptance step for each materially new conversion behavior.

## License

Licensed under the MIT License. See [LICENSE](LICENSE) for the full text.
