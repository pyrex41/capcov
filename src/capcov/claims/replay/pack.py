"""Installed replay profiles.

V1 remains the frozen compatibility pack. V2 is generated from
``specs/claims/replay.claims`` by native Shen elaboration; installed evaluation
loads JSON and needs neither the checkout nor Shen. Select a version once at
``join.build`` and carry that profile through export and evaluation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..ir import Bundle
from .. import pack_resources as _resources

PACK_ID = "rules-replay-v1"
PACK_NAME = "rules-replay-v1.json"
#: The shipped mirror: package data, present in a source checkout and in a wheel.
PACK_PATH = Path(__file__).resolve().parent / PACK_NAME

DIAGNOSTIC_POLICY = _resources.DIAGNOSTIC_POLICY
RELATION_FIELDS = _resources.RELATION_FIELDS


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_pack_text(version: int = 1) -> str:
    """The shipped pack's bytes, as ``importlib.resources`` hands them over."""
    return _resources.read_pack_text("replay", version)


def load_pack(path: Path | None = None, *, version: int = 1) -> dict[str, Any]:
    """The rule pack document.  ``path=None`` reads the shipped package data."""
    return _resources.load_pack("replay", version, path=path)


def pack_relations(pack: dict[str, Any]) -> list[dict[str, Any]]:
    return _resources.pack_relations(pack)


def pack_bundle(pack: dict[str, Any] | None = None, *, version: int = 1) -> Bundle:
    """The rule pack alone (declarations and rules, no facts) as a validated Bundle."""
    return _resources.pack_bundle(load_pack(version=version) if pack is None else pack)


#: The reviewed original this file mirrors is
#: ``experiments/claim-semantics/replay/rules-replay-v1.json``, a repository
#: path.  It is deliberately NOT a constant here: an installed module that
#: names a repository directory is the defect this loader was changed to
#: remove.  The tests, which do live in the repository, own that path
#: (``tests/claim_semantics/test_replay_pack_package_data.py``).
__all__ = ["PACK_PATH", "PACK_NAME", "PACK_ID", "DIAGNOSTIC_POLICY", "RELATION_FIELDS",
           "read_json", "read_pack_text", "load_pack", "pack_relations", "pack_bundle"]
