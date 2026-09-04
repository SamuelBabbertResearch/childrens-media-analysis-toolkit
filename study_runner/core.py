"""Adult-only package validation and durable participant response storage.

This module uses only the Python standard library. The participant executable
must not pull CMAT's analysis dependencies into its bundle merely to present
already-frozen media and record ratings.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2
RATING_VALUES = (1, 2, 3, 4, 5)
BLOCK_TYPE = "adult_self"
RESPONSE_SEQUENCE = "adult_self"
RESPONSE_FIELDS = (
    "recorded_at_utc", "study_id", "package_hash", "session_id",
    "participant_id", "block_type", "question_id", "clip_id",
    "source_file_id", "trial_order", "counterbalance_condition", "rating",
    "response_sequence", "completion_status",
)
ASSIGNMENT_FIELDS = (
    "assigned_at_utc", "study_id", "package_hash", "session_id",
    "participant_id", "assignment_sequence", "counterbalance_condition",
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


class PackageError(ValueError):
    """The study package is incomplete, inconsistent, or has changed."""


@dataclass(frozen=True)
class Stimulus:
    label: str
    source_file_id: str
    pair_id: str
    path: Path
    sha256: str


@dataclass(frozen=True)
class StudyPackage:
    root: Path
    study_id: str
    status: str
    title: str
    question_id: str
    question: str
    instructions: tuple[str, ...]
    practice_prompt: str
    practice_expected_rating: int
    debrief: str
    anchors: tuple[str, ...]
    stimuli: tuple[Stimulus, ...]
    order_conditions: dict[str, tuple[str, ...]]
    package_hash: str
    raw: dict[str, Any]

    def stimulus(self, label: str) -> Stimulus:
        try:
            return next(s for s in self.stimuli if s.label == label)
        except StopIteration as exc:
            raise PackageError(f"Unknown stimulus label: {label}") from exc

    def order(self, condition: str) -> tuple[Stimulus, ...]:
        if condition not in self.order_conditions:
            raise PackageError(f"Unknown order condition: {condition}")
        return tuple(self.stimulus(label)
                     for label in self.order_conditions[condition])


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _required_text(raw: dict[str, Any], key: str) -> str:
    value = str(raw.get(key, "")).strip()
    if not value:
        raise PackageError(f"{key} must be a non-empty string")
    return value


def load_package(folder: Path | str, *, allow_draft: bool = False,
                 verify_media: bool = True) -> StudyPackage:
    """Load and fail-closed validate ``study_config.json`` in *folder*.

    Schema version 2 is intentionally incompatible with the superseded package:
    a package that contains the adult-prediction/child protocol cannot be opened
    accidentally by the adult-only runner.
    """
    root = Path(folder).resolve()
    config_path = root / "study_config.json"
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PackageError(f"Missing {config_path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageError(f"Cannot read study configuration: {exc}") from exc

    if raw.get("schema_version") != SCHEMA_VERSION:
        raise PackageError(
            f"Adult-only Study Runner requires schema_version {SCHEMA_VERSION}")
    if "target_age_wording" in raw:
        raise PackageError("Adult-only packages cannot contain target_age_wording")

    study_id = str(raw.get("study_id", "")).strip()
    if not _SAFE_ID.fullmatch(study_id):
        raise PackageError("study_id must be a safe, non-empty identifier")
    status = str(raw.get("status", "draft")).strip().lower()
    if status not in {"draft", "pilot", "approved"}:
        raise PackageError("status must be draft, pilot, or approved")
    if status == "draft" and not allow_draft:
        raise PackageError("Draft package cannot start participant sessions")

    title = _required_text(raw, "study_title")
    question_id = _required_text(raw, "question_id")
    question = _required_text(raw, "participant_question")
    if question != "How fast did this video feel?":
        raise PackageError("participant_question does not match the adult-only protocol")
    instructions = tuple(str(item).strip()
                         for item in raw.get("instructions", ()))
    if len(instructions) < 3 or any(not item for item in instructions):
        raise PackageError("instructions must contain at least three non-empty items")
    practice = raw.get("practice", {})
    if not isinstance(practice, dict):
        raise PackageError("practice must be an object")
    practice_prompt = str(practice.get("prompt", "")).strip()
    practice_expected = practice.get("expected_rating")
    if not practice_prompt or practice_expected not in RATING_VALUES:
        raise PackageError("practice must have a prompt and expected_rating from 1 to 5")
    debrief = _required_text(raw, "debrief")

    anchors = tuple(str(a).strip() for a in raw.get("rating_anchors", ()))
    if anchors != ("Very slow", "Slow", "In between", "Fast", "Very fast"):
        raise PackageError("rating_anchors do not match the adult-only protocol")

    stimuli: list[Stimulus] = []
    labels: set[str] = set()
    file_ids: set[str] = set()
    media_paths: set[Path] = set()
    media_hashes: set[str] = set()
    for item in raw.get("stimuli", ()):
        label = str(item.get("label", "")).strip()
        file_id = str(item.get("source_file_id", "")).strip()
        pair_id = str(item.get("pair_id", "")).strip()
        relative = Path(str(item.get("file", "")))
        expected = str(item.get("sha256", "")).strip().lower()
        if not label or label in labels:
            raise PackageError(f"Missing or duplicate clip label: {label!r}")
        if not file_id or file_id in file_ids:
            raise PackageError(f"Missing or duplicate source_file_id: {file_id!r}")
        if not pair_id:
            raise PackageError(f"Stimulus {label} has no pair_id")
        if relative.is_absolute() or ".." in relative.parts:
            raise PackageError(f"Stimulus {label} must use a package-relative file")
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise PackageError(f"Stimulus {label} escapes the package") from exc
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise PackageError(f"Stimulus {label} has no valid SHA-256")
        if path in media_paths:
            raise PackageError(f"Stimulus file is reused: {relative}")
        if expected in media_hashes:
            raise PackageError(f"Stimulus content is duplicated: {label}")
        if verify_media:
            if not path.is_file():
                raise PackageError(f"Stimulus file is missing: {relative}")
            actual = sha256_file(path)
            if actual != expected:
                raise PackageError(f"Stimulus checksum mismatch: {label}")
        labels.add(label)
        file_ids.add(file_id)
        media_paths.add(path)
        media_hashes.add(expected)
        stimuli.append(Stimulus(label, file_id, pair_id, path, expected))
    if status != "draft" and len(stimuli) != 12:
        raise PackageError("Pilot/approved packages must contain exactly 12 stimuli")

    orders: dict[str, tuple[str, ...]] = {}
    for name, sequence in raw.get("order_conditions", {}).items():
        key = str(name).strip()
        order = tuple(str(label).strip() for label in sequence)
        if not key or key in orders:
            raise PackageError("Order-condition names must be unique and non-empty")
        if len(order) != len(labels) or set(order) != labels:
            raise PackageError(f"Order {key} is not a permutation of all stimuli")
        orders[key] = order
    if status != "draft":
        if len(orders) != 2:
            raise PackageError("Adult-only pilot/approved packages require two orders")
        first, second = orders.values()
        if second != tuple(reversed(first)):
            raise PackageError("The second order must be the reverse of the first")

    return StudyPackage(
        root, study_id, status, title, question_id, question, instructions,
        practice_prompt, int(practice_expected), debrief, anchors,
        tuple(stimuli), orders, _canonical_hash(raw), raw)


class ResponseStore:
    """Durable adult-only response writer with automatic alternating orders."""

    def __init__(self, data_dir: Path | str, package: StudyPackage,
                 participant_id: str) -> None:
        if not _SAFE_ID.fullmatch(participant_id):
            raise ValueError("Participant ID may contain letters, numbers, . _ or -")
        self.package = package
        self.participant_id = participant_id
        self.session_id = (
            f"{participant_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-"
            f"{uuid.uuid4().hex[:8]}")
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.responses_path = self.data_dir / "responses.csv"
        self.assignments_path = self.data_dir / "assignments.csv"
        self.state_path = self.data_dir / f"session_{self.session_id}.json"
        self._keys: set[str] = set()
        self.assignment_sequence, self.condition = self._assign_condition()
        self._write_state({"status": "started", "next_trial": 1,
                           "next_block": BLOCK_TYPE})

    def _assign_condition(self) -> tuple[int, str]:
        rows: list[dict[str, str]] = []
        if self.assignments_path.exists():
            with self.assignments_path.open(newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                if tuple(reader.fieldnames or ()) != ASSIGNMENT_FIELDS:
                    raise ValueError("assignments.csv uses an incompatible schema")
                rows = list(reader)
        if any(row["participant_id"] == self.participant_id for row in rows):
            raise ValueError("That participant ID has already been assigned")
        sequence = len(rows) + 1
        conditions = tuple(self.package.order_conditions)
        if not conditions:
            raise ValueError("The package has no order conditions")
        condition = conditions[(sequence - 1) % len(conditions)]
        row = {
            "assigned_at_utc": datetime.now(timezone.utc).isoformat(),
            "study_id": self.package.study_id,
            "package_hash": self.package.package_hash,
            "session_id": self.session_id,
            "participant_id": self.participant_id,
            "assignment_sequence": sequence,
            "counterbalance_condition": condition,
        }
        self._append_csv(self.assignments_path, ASSIGNMENT_FIELDS, row)
        return sequence, condition

    @staticmethod
    def _append_csv(path: Path, fields: tuple[str, ...], row: dict[str, Any]) -> None:
        exists = path.exists()
        if exists:
            with path.open(newline="", encoding="utf-8") as check:
                reader = csv.reader(check)
                header = tuple(next(reader, ()))
            if header != fields:
                raise ValueError(f"{path.name} uses an incompatible schema")
        with path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            if not exists:
                writer.writeheader()
            writer.writerow(row)
            fh.flush()
            os.fsync(fh.fileno())

    def append_rating(self, *, stimulus: Stimulus, trial_order: int,
                      rating: int) -> None:
        """Append one confirmed adult self-perception rating."""
        if rating not in RATING_VALUES:
            raise ValueError("rating must be an integer from 1 through 5")
        self._append_response(stimulus=stimulus, trial_order=trial_order,
                              rating=rating, completion_status="completed")

    def append_skip(self, *, stimulus: Stimulus, trial_order: int) -> None:
        """Represent an intentionally unanswered trial without inventing a rating."""
        self._append_response(stimulus=stimulus, trial_order=trial_order,
                              rating="", completion_status="skipped")

    def _append_response(self, *, stimulus: Stimulus, trial_order: int,
                         rating: int | str, completion_status: str) -> None:
        if stimulus.label in self._keys:
            raise ValueError("That response is already locked")
        if not 1 <= trial_order <= len(self.package.stimuli):
            raise ValueError("trial_order is outside the frozen stimulus sequence")
        row = {
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "study_id": self.package.study_id,
            "package_hash": self.package.package_hash,
            "session_id": self.session_id,
            "participant_id": self.participant_id,
            "block_type": BLOCK_TYPE,
            "question_id": self.package.question_id,
            "clip_id": stimulus.label,
            "source_file_id": stimulus.source_file_id,
            "trial_order": trial_order,
            "counterbalance_condition": self.condition,
            "rating": rating,
            "response_sequence": RESPONSE_SEQUENCE,
            "completion_status": completion_status,
        }
        self._append_csv(self.responses_path, RESPONSE_FIELDS, row)
        self._keys.add(stimulus.label)

    def checkpoint(self, *, status: str, next_trial: int,
                   next_block: str = "") -> None:
        self._write_state({"status": status, "next_trial": next_trial,
                           "next_block": next_block})

    def withdraw(self) -> None:
        """Delete this still-identifiable session's ratings and mark withdrawal.

        The assignment ledger remains so the anonymous code cannot accidentally
        enroll twice; it contains no rating data.
        """
        if self.responses_path.exists():
            with self.responses_path.open(newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                if tuple(reader.fieldnames or ()) != RESPONSE_FIELDS:
                    raise ValueError("responses.csv uses an incompatible schema")
                retained = [row for row in reader
                            if row["session_id"] != self.session_id]
            fd, temp_name = tempfile.mkstemp(prefix=self.responses_path.name,
                                             dir=self.data_dir)
            try:
                with os.fdopen(fd, "w", newline="", encoding="utf-8") as fh:
                    writer = csv.DictWriter(fh, fieldnames=RESPONSE_FIELDS)
                    writer.writeheader()
                    writer.writerows(retained)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(temp_name, self.responses_path)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
        self._keys.clear()
        self._write_state({"status": "withdrawn", "next_trial": 0,
                           "next_block": ""})

    def _write_state(self, progress: dict[str, Any]) -> None:
        payload = {
            "study_id": self.package.study_id,
            "package_hash": self.package.package_hash,
            "session_id": self.session_id,
            "participant_id": self.participant_id,
            "assignment_sequence": self.assignment_sequence,
            "counterbalance_condition": self.condition,
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            **progress,
        }
        fd, temp_name = tempfile.mkstemp(prefix=self.state_path.name,
                                         dir=self.data_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temp_name, self.state_path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
