# Contributing

Read `AGENTS.md`, `docs/ARCHITECTURE.md`, and `docs/AGENT_SOURCES.md` first. Verify every Kodi or Servarr contract against current official source or the target instance OpenAPI schema.

Required before a pull request:

```bash
python -m pip install -r requirements-dev.txt
python scripts/validate.py
ruff check .
python -m unittest discover -s tests -v
SOURCE_DATE_EPOCH=1700000000 python scripts/package.py
```

Changes to destructive behaviour require tests for ambiguity, cancellation, dry run, partial commit, path boundaries, command failure and multi-episode files. Never include real API keys, private URLs or media paths in fixtures.
