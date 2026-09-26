"""Guards that keep real budget plans out of the repository."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_DIRS = {"examples", "tests", ".github"}
SKIPPED_DIRS = {".git", ".venv", "private", ".mypy_cache", ".pytest_cache", ".ruff_cache"}


def test_yaml_files_live_only_in_allowed_folders() -> None:
    stray = [
        path.relative_to(ROOT)
        for pattern in ("*.yaml", "*.yml")
        for path in ROOT.rglob(pattern)
        if not SKIPPED_DIRS.intersection(path.relative_to(ROOT).parts)
        and path.relative_to(ROOT).parts[0] not in ALLOWED_DIRS
    ]
    assert stray == []


def test_private_folder_is_git_ignored() -> None:
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "private/" in ignored
