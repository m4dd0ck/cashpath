"""The demo plan and the Streamlit script ship inside the package, so installed copies find them."""

from pathlib import Path

import cashpath
from cashpath.cli import APP_SCRIPT
from cashpath.plan import DEMO_PLAN

PACKAGE_DIR = Path(cashpath.__file__).resolve().parent


def test_demo_plan_is_inside_the_package() -> None:
    assert DEMO_PLAN.parent == PACKAGE_DIR
    assert DEMO_PLAN.is_file()


def test_app_script_is_inside_the_package() -> None:
    assert APP_SCRIPT.parent == PACKAGE_DIR
    assert APP_SCRIPT.is_file()


def test_app_script_runs_main_when_executed_as_a_script() -> None:
    # Reason: `streamlit run` executes the file with __name__ == "__main__"
    assert 'if __name__ == "__main__":\n    main()' in APP_SCRIPT.read_text(encoding="utf-8")
