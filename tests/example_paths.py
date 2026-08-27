from pathlib import Path

# FLYNC repository root (parent of the tests/ directory). Files in tests/ and
# its subdirectories live at varying depths, so resolve from __file__ instead of
# repeating fragile `Path(__file__).parents[N]` expressions per test module.
_REPO_ROOT = Path(__file__).resolve().parent.parent

FLYNC_EXAMPLE = _REPO_ROOT / "examples" / "flync_example"

FLYNC_EXAMPLE_EXPERIMENTAL = _REPO_ROOT / "examples" / "flync_example_experimental"
