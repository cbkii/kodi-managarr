# Codex execution profile

Codex must read and obey the root `AGENTS.md`; its scope covers the entire repository. Read `docs/AGENT_SOURCES.md` before modifying Kodi or Servarr contracts.

## Working method

- Inspect the repository and relevant tests before editing.
- Use official docs, live OpenAPI, and matching upstream source for external behaviour.
- Prefer focused patches over speculative rewrites.
- Complete implementation, tests, documentation and validation in the same task.
- Do not finish with uncommitted generated ZIPs, temporary diagnostics, credentials, or a dirty worktree.
- When tool/network access is unavailable, preserve the fail-closed design and state exactly what could not be externally verified.

## Required commands

```bash
set -euo pipefail
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
python3 scripts/package.py
```

Inspect the generated ZIP as required by `AGENTS.md`, then remove `dist/` unless release artefacts are explicitly part of the task.

## Implementation priorities

1. Destructive safety and transaction ordering.
2. Correct version-specific Kodi/Servarr contracts.
3. Android TV and Kodi VFS compatibility.
4. Deterministic, host-runnable tests.
5. Clear errors, secret redaction and bounded operations.
6. Minimal scope and maintainable separation of concerns.

## Review behaviour

For review tasks, lead with actionable correctness, data-loss, compatibility, security, and testing findings. Cite exact files/lines and trace failures through the full workflow. Do not report stylistic preferences as blockers unless they cause a concrete maintenance or correctness issue.

## Final response

Include summary, files changed, exact test/validation results, sources consulted, device/integration-test status, and residual risk. Only claim tests that actually ran.

References:

- https://openai.com/index/introducing-codex/
- https://platform.openai.com/docs/codex/overview
