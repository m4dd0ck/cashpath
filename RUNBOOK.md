# Runbook

Procedures for cashpath. `README.md` describes what each command does; this file says when to
run it and in what order.

## On open

```bash
git status --short
git log -3 --oneline
```

## On close

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q
```

## Run

`uv run cashpath forecast` on the demo plan; `uv run cashpath app` for the Streamlit app. Pass
a plan file from `private/` to run on real numbers. The app can also be started as
`uv run streamlit run streamlit_app.py`, which is what the cloud does.

## Release

1. Bump `version` in `pyproject.toml` and `__version__` in `cashpath/__init__.py`, then
   `uv lock` (CI installs with `--locked`).
2. Commit `chore: Release vX.Y.Z`, tag `git tag -a vX.Y.Z`, push `main` and the tag.
3. `gh release create vX.Y.Z` with handwritten notes; mark it latest.

## Deploy

Nothing by hand. Streamlit Community Cloud watches `main` and redeploys the app on every push;
it installs from `uv.lock`. After a push that touches the app, open the demo URL in the README
and check the forecast page renders. A broken deploy shows its log in the app's "Manage app"
panel on the Streamlit Cloud dashboard.

## Restore on a new machine

1. Clone the repo, `uv sync`.
2. Copy a plan into `private/` from your own copy; there is none in git (the folder is gitignored; create it). The demo plan works
   without one.
3. `uv run pytest`, then `uv run cashpath forecast`.

## Validate

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run pytest
uv run cashpath forecast
```
