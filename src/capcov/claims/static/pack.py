"""Installed static rule profiles, with the same loading boundary as other domains.

V1 remains the frozen compatibility pack and the default. V2 is generated from
``specs/claims/static.claims`` by native Shen elaboration and is refused unless
its pack, schema and stubs match the specification manifest; installed
evaluation loads JSON and needs neither the checkout nor Shen. Select a version
once at the export entry point and carry that profile through evaluation.
"""
from pathlib import Path
from .. import pack_resources as _resources
from ..pack_resources import DIAGNOSTIC_POLICY, RELATION_FIELDS, pack_relations

PACK_ID = 'rules-static-v1'
PACK_NAME = PACK_ID + '.json'
PACK_PATH = Path(__file__).resolve().parent / PACK_NAME


def read_pack_text(version=1):
    return _resources.read_pack_text('static', version)


def load_pack(path=None, *, version=1):
    return _resources.load_pack('static', version, path=path)


def pack_bundle(pack=None, *, version=1):
    return _resources.pack_bundle(load_pack(version=version) if pack is None else pack)
