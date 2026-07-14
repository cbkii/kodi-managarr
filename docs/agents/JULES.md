# Jules execution profile

Jules automatically reads the root `AGENTS.md`. Treat it as mandatory and read `docs/AGENT_SOURCES.md` before changing any Kodi or Servarr integration.

## Environment setup

Jules tasks run in a short-lived Ubuntu VM. This repository has no third-party host-side Python dependencies.

Use this lightweight setup/validation sequence:

```bash
set -euo pipefail
python3 --version
git status --short
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
```

Do not attempt to install Kodi, Android SDKs, Radarr, Sonarr, Prowlarr, Samba, Paramiko, or system services for ordinary unit-test work. Use mocks/fakes. Add an opt-in sandbox integration test only when the task explicitly requires it.

## Task behaviour

1. Read the task, `AGENTS.md`, architecture, source knowledgebase, relevant code/tests, and complete PR discussion.
2. Produce a concrete plan, then continue autonomously after plan approval.
3. Verify external contracts through the linked official source rather than guessing.
4. Implement the complete solution, including failure handling, tests and documentation.
5. Run validation, unit tests and package verification after the final edit.
6. Inspect the final diff and leave the branch in a coherent, reviewable state.

Do not pause for routine implementation choices that can be resolved from the repository or sources. Make the safest compatible engineering decision and explain it in the final summary.

## Review and CI work

- Read full comments, review threads and logs, including collapsed/truncated sections.
- Reproduce failures locally where possible.
- Classify feedback before acting; do not implement stale or invalid suggestions blindly.
- Fix all valid in-scope issues and add regression tests.
- Resolve a thread only after the code/tests fully address it.
- Do not weaken destructive safeguards simply to satisfy a test or reviewer suggestion.

## Completion evidence

Report:

- files and behaviour changed;
- official/upstream sources consulted;
- `python3 scripts/validate.py` result;
- `python3 -m unittest discover -s tests -v` result;
- `python3 scripts/package.py` and ZIP verification result;
- any Android TV/Kodi or live Servarr testing not performed;
- remaining risks.

Reference: https://jules.google/docs/ and https://jules.google/docs/environment/
