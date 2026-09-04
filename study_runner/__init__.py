"""Lean participant-facing study runner; intentionally independent of analyzer."""

from .core import PackageError, StudyPackage, load_package

__all__ = ["PackageError", "StudyPackage", "load_package"]
