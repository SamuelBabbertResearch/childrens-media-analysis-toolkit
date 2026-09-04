"""Entry point for the separate CMAT Study Runner executable."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Run a frozen CMAT study package")
    parser.add_argument("--package", type=Path,
                        help="folder containing study_config.json")
    parser.add_argument("--data-dir", type=Path,
                        help="append-only response output folder")
    parser.add_argument("--allow-draft", action="store_true",
                        help="developer preview only; never use for collection")
    return parser.parse_args(argv)


def _application_dir() -> Path:
    """Folder beside the executable when frozen, repository root in source."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    args = _args(argv)
    from study_runner.core import PackageError, load_package
    try:
        from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
        from study_runner.window import StudyRunnerWindow
    except ImportError as exc:
        print(f"PySide6 with Qt Multimedia is required: {exc}", file=sys.stderr)
        return 1
    app = QApplication(sys.argv[:1])
    base = _application_dir()
    package_dir = args.package.resolve() if args.package else base / "study"
    while True:
        try:
            package = load_package(package_dir, allow_draft=args.allow_draft)
            break
        except PackageError as exc:
            if args.package is not None:
                QMessageBox.critical(None, "Study package refused", str(exc))
                return 2
            answer = QMessageBox.warning(
                None, "Study package needed",
                f"CMAT Study Runner could not open the study package beside it.\n\n"
                f"{exc}\n\nChoose the folder containing study_config.json?",
                QMessageBox.Open | QMessageBox.Cancel, QMessageBox.Open)
            if answer != QMessageBox.Open:
                return 2
            chosen = QFileDialog.getExistingDirectory(
                None, "Choose study package", str(base))
            if not chosen:
                return 2
            package_dir = Path(chosen)
    data_dir = args.data_dir.resolve() if args.data_dir else base / "participant_data"
    window = StudyRunnerWindow(package, data_dir)
    window.show()
    if package.status == "draft":
        QMessageBox.warning(window, "Draft preview",
                            "This package is not approved for participant data collection.")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
