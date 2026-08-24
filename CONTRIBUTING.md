# Contributing

## Scope

Keep the two workflow boundaries intact:

- `chatcut-a-roll-hard-cut` owns spoken-content selection and natural hard-cut boundaries only.
- `chatcut-final-cut-compound-handoff` owns cuts-only XML handoff only.

Do not add visual finishing, motion transfer, B-roll, captions, music, or automatic Final Cut UI operation to either package without first redefining the public contract in a major version.

## Changes

1. Create a short feature or fix branch.
2. Change only the affected skill and shared tests.
3. Add or update a synthetic fixture for conversion behavior.
4. Run repository validation and tests.
5. Update `CHANGELOG.md` and the affected `VERSION` when preparing a release.

Never use real media or project XML as a committed fixture. Reduce a case to the smallest synthetic XML that reproduces the structure.
