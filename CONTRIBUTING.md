# Contributing

Use small branches and pull requests targeting `main`. Write documentation, comments,
docstrings, interface text, PR descriptions and future commit messages in English.
Keep multilingual search data and fixtures in their original languages.

## Local checks

Install [uv](https://docs.astral.sh/uv/), then run:

```sh
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run ty check src/anna
uv run pytest -q
uv build
uv run twine check dist/*
```

Use `uv lock` when changing dependencies and commit `uv.lock`. Run relevant tests
while developing; run all local gates before a release. CI checks Linux, macOS and
Windows and installs built wheels outside the source checkout.

## Packaging tests

```sh
uv sync --locked --group bundle
uv run --frozen --group bundle python scripts/build_binary.py --target linux-x86_64
uv run --frozen python scripts/test_installers.py
```

Choose the native host target for non-Linux machines. The builder refuses cross builds
and runs `scripts/smoke_test.py` against the executable before archiving it. Local fixture
HTTP servers exercise JSON output, redirects, binary downloads, checksums, no-overwrite
behavior and error handling. Unit fixtures and packaged tests require no external accounts.

## Changes to scraping behavior

Include a minimal, sanitized fixture illustrating the actual layout change and explain
its provenance. Never commit Cookies, private book records, account information or files
with embedded credentials. Keep challenge pages distinct from empty search results.
Do not make live AA requests a required PR check.

## Public interface

`src/anna/__init__.py` is the package version source. Treat command names, options,
JSON fields, error codes and exit statuses as interfaces. Avoid breaking changes without
release notes. Progress must stay out of JSON stdout. Add behavioral tests for relevant
failure paths, not tests that merely repeat implementation details.
