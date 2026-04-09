"""Canonical-object ID derivation.

Canonical objects are identified by a deterministic UUID derived from the
triple (language, type, canonical_form) using UUID v5.

Using a deterministic UUID means:
  - The same word encountered in different texts always maps to the same
    canonical object without a database round-trip.
  - The parse route can return stable IDs even when the database is
    temporarily unavailable.
  - Review state stored in the database remains valid across re-parses and
    server restarts.

WARNING: changing _NAMESPACE invalidates every UUID stored in the database
(canonical_objects PKs, review_states.object_id).  Treat it as immutable.
"""
from __future__ import annotations

import uuid

# Fixed namespace UUID — do not change after first deployment.
_NAMESPACE = uuid.UUID("12e3d947-f3c4-4e2b-a9a1-0d3c2e1f5b7a")


def canonical_object_id(language: str, type_: str, canonical_form: str) -> str:
    """Return a stable UUID string for a canonical learnable object.

    Null bytes separate the three fields to prevent collisions such as
    ("es", "voc", "ab:cd") vs ("es", "vocab", "cd").
    """
    key = f"{language}\x00{type_}\x00{canonical_form}"
    return str(uuid.uuid5(_NAMESPACE, key))
