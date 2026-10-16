"""Load the reviewed observation rule pack (``rules-observation-v1.json``) as a validated Bundle.

The pack **ships as package data** beside this module -- exactly as
``schema_observation_v1.json`` does -- and is read through
``importlib.resources``, so ``capcov.claims.observation.join`` builds the
judge's combined bundle from an installed wheel with no source tree on disk.

Unlike ``capcov.claims.replay.pack`` there is **no reviewed original
elsewhere**: v1 ships no ``experiments/claim-semantics/observation/`` mirror,
because no corpus adapter reads observation receipts yet and a mirror nobody
reads is only a second opinion waiting to drift.  The file beside this module
is the reviewed file.

The pack is kept in raw IR JSON wire form and merged verbatim: every relation
declaration and rule comes from the file, nothing is evaluated here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..ir import Bundle
from .. import pack_resources as _resources

PACK_ID = "rules-observation-v1"
PACK_NAME = "rules-observation-v1.json"
#: The shipped pack: package data, present in a source checkout and in a wheel.
PACK_PATH = Path(__file__).resolve().parent / PACK_NAME

DIAGNOSTIC_POLICY = _resources.DIAGNOSTIC_POLICY
RELATION_FIELDS = _resources.RELATION_FIELDS


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_pack_text() -> str:
    """The shipped pack's bytes, as ``importlib.resources`` hands them over."""
    return _resources.read_pack_text("observation")


def load_pack(path: Path | None = None) -> dict[str, Any]:
    """The rule pack document.  ``path=None`` reads the shipped package data."""
    return _resources.load_pack("observation", path=path)


def pack_relations(pack: dict[str, Any]) -> list[dict[str, Any]]:
    return _resources.pack_relations(pack)


def pack_bundle(pack: dict[str, Any] | None = None) -> Bundle:
    """The rule pack alone (declarations and rules, no facts) as a validated Bundle."""
    return _resources.pack_bundle(load_pack() if pack is None else pack)


__all__ = ["PACK_PATH", "PACK_NAME", "PACK_ID", "DIAGNOSTIC_POLICY", "RELATION_FIELDS",
           "read_json", "read_pack_text", "load_pack", "pack_relations", "pack_bundle"]
