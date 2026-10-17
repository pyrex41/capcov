"""Versioned, installed-package-only rule resource transport.

This layer neither combines conflicting declarations nor chooses a version on
behalf of an exporter. Callers select the version before loading resources.
"""
from importlib import resources
from dataclasses import dataclass
import hashlib
import json
from .ir import Bundle, bundle_from_json

DOMAINS = frozenset({'static', 'replay', 'observation'})
#: Domains with a generated, manifest-checked v2 profile. V1 stays the default.
V2_DOMAINS = frozenset({'static', 'replay'})
RELATION_FIELDS = frozenset({'name','columns','modality','polarity','binding','primitive',
    'producer_classes','context_indices','completes','finite','nonempty',
    'compatibility_targets','compatibility_context_indices'})
DIAGNOSTIC_POLICY = {'missing_premises':'unresolved','inconsistent_premises':'inconsistent-premises',
    'out_of_scope':'out-of-scope','forbidden_evidence':'invalid-input','revocation':'refutation','completeness':'required'}


def read_pack_text(domain, version=1):
    if domain not in DOMAINS or type(version) is not int or version not in ((1, 2) if domain in V2_DOMAINS else (1,)):
        raise ValueError(f'unsupported installed pack profile: {domain}/v{version}')
    directory = resources.files(f'capcov.claims.{domain}')
    raw = directory.joinpath(f'rules-{domain}-v{version}.json').read_bytes()
    if version == 2:
        manifest = json.loads(directory.joinpath(f'rules-{domain}-v2.manifest.json').read_text(encoding='utf-8'))
        files = {'pack.json': raw,
                 'schema.json': directory.joinpath(f'schema_{domain}_v2.json').read_bytes(),
                 'stubs.json': directory.joinpath(f'stubs-{domain}-v2.json').read_bytes()}
        if (manifest.get('pack_id') != f'rules-{domain}-v2' or manifest.get('bundle_schema_version') != 2
            or any(hashlib.sha256(content).hexdigest() != manifest.get('artifacts', {}).get(name)
                   for name,content in files.items())):
            raise ValueError('installed pack artifacts do not match their specification manifest')
    return raw.decode('utf-8')


def load_pack(domain, version=1, path=None):
    # Check the requested profile even when a custom path is supplied.
    if domain not in DOMAINS or type(version) is not int or version not in ((1, 2) if domain in V2_DOMAINS else (1,)):
        raise ValueError(f'unsupported installed pack profile: {domain}/v{version}')
    text = path.read_text(encoding='utf-8') if path is not None else read_pack_text(domain,version)
    pack = json.loads(text)
    if pack.get('schema_version') != version or pack.get('id') != f'rules-{domain}-v{version}':
        raise ValueError(f'unsupported {domain} rule pack')
    for section in ('primitives','supplementary_primitives','derived','rules'):
        if not isinstance(pack.get(section),list):
            raise ValueError(f'rule pack section {section!r} must be a list')
    return pack


def pack_relations(pack):
    relations = [*pack['primitives'],*pack['supplementary_primitives'],*pack['derived']]
    names = [r['name'] for r in relations]
    if len(names) != len(set(names)):
        raise ValueError('rule pack declares a relation twice')
    for relation in relations:
        if set(relation) != RELATION_FIELDS:
            raise ValueError(f"relation {relation.get('name')!r} has unknown or missing fields")
    return relations


def pack_bundle(pack):
    from .contracts import CONTRACT_FIELDS
    return bundle_from_json(dict(schema_version=pack['schema_version'],relations=pack_relations(pack),
                                  rules=pack['rules'],diagnostic_policy=DIAGNOSTIC_POLICY,
                                  **{key:pack[key] for key in CONTRACT_FIELDS if key in pack}))


@dataclass(frozen=True)
class PackProfile:
    domain: str
    version: int
    id: str
    bundle: Bundle
    manifest_digest: str = ""


def resolve_profile(domain, version=1):
    """Resolve once at an outer entry point, then pass the immutable selection."""
    pack = load_pack(domain, version)
    manifest_digest = ''
    if version == 2:
        raw = resources.files(f'capcov.claims.{domain}').joinpath(f'rules-{domain}-v2.manifest.json').read_bytes()
        manifest_digest = hashlib.sha256(raw).hexdigest()
    return PackProfile(domain, version, pack['id'], pack_bundle(pack), manifest_digest)
