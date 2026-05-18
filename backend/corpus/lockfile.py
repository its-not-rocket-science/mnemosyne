"""Lockfile support for the corpus build pipeline.

``corpora/manifest.lock.json`` is a flat JSON object whose keys are
``manifest_id`` values and whose values are ``LockEntry`` dicts.  The
lockfile is updated atomically (write to a temp file, then rename) so a
crash during write never leaves a half-written file.

This file is checked in to version control so that CI and team members
share URL verification state and ingestion status without needing DB access.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

DEFAULT_LOCKFILE = Path("corpora/manifest.lock.json")


class LockEntry(TypedDict, total=False):
    manifest_entry_hash:     str
    raw_content_hash:        str | None
    normalized_content_hash: str | None
    cached_path:             str | None
    verified_url:            str | None
    last_verified_at:        str | None
    ingestion_status:        str
    """pending | ok | failed | skipped | metadata_only"""


def load_lockfile(path: Path = DEFAULT_LOCKFILE) -> dict[str, LockEntry]:
    """Return the lockfile contents, or an empty dict if the file does not exist."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_lockfile(data: dict[str, LockEntry], path: Path = DEFAULT_LOCKFILE) -> None:
    """Write *data* to *path* atomically (temp-file + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".lock.tmp.", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def update_lock_entry(
    data: dict[str, LockEntry],
    manifest_id: str,
    *,
    manifest_entry_hash: str | None = None,
    raw_content_hash: str | None = None,
    normalized_content_hash: str | None = None,
    cached_path: str | None = None,
    verified_url: str | None = None,
    verify: bool = False,
    ingestion_status: str | None = None,
) -> LockEntry:
    """Update a single entry in the lockfile data dict (in place) and return it."""
    entry: LockEntry = dict(data.get(manifest_id, {}))  # type: ignore[arg-type]
    if manifest_entry_hash is not None:
        entry["manifest_entry_hash"] = manifest_entry_hash
    if raw_content_hash is not None:
        entry["raw_content_hash"] = raw_content_hash
    if normalized_content_hash is not None:
        entry["normalized_content_hash"] = normalized_content_hash
    if cached_path is not None:
        entry["cached_path"] = cached_path
    if verified_url is not None:
        entry["verified_url"] = verified_url
    if verify:
        entry["last_verified_at"] = datetime.now(timezone.utc).isoformat()
    if ingestion_status is not None:
        entry["ingestion_status"] = ingestion_status
    data[manifest_id] = entry
    return entry
