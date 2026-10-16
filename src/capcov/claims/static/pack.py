"""Installed static rule pack, with the same loading boundary as other domains."""
from pathlib import Path
from .. import pack_resources as _resources
from ..pack_resources import DIAGNOSTIC_POLICY, RELATION_FIELDS, pack_relations

PACK_ID = 'rules-static-v1'
PACK_NAME = PACK_ID + '.json'
PACK_PATH = Path(__file__).resolve().parent / PACK_NAME


def read_pack_text():
    return _resources.read_pack_text('static')


def load_pack(path=None):
    return _resources.load_pack('static',path=path)


def pack_bundle(pack=None):
    return _resources.pack_bundle(load_pack() if pack is None else pack)
