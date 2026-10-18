"""Explicit, immutable evidence-composition declarations for Bundle schema 2.

These records contain data only. They neither admit evidence nor create closure
facts. Schema 1 deliberately does not serialize these fields.
"""
from __future__ import annotations
from dataclasses import dataclass


def _names(value, field):
    if not isinstance(value, (tuple, list)):
        raise TypeError(f"{field} must be an array of names")
    value = tuple(value)
    if any(not isinstance(x, str) or not x for x in value):
        raise TypeError(f"{field} must contain nonempty names")
    if len(value) != len(set(value)):
        raise ValueError(f"duplicate {field}")
    return tuple(sorted(value))


def _text(record, *fields):
    for field in fields:
        if not isinstance(getattr(record, field), str) or not getattr(record, field):
            raise TypeError(f"{field} must be a nonempty name")


@dataclass(frozen=True)
class CompatibilityCapability:
    name: str
    witness: str
    left_dimension: str
    right_dimension: str
    left_column: str
    right_column: str
    left_targets: tuple[str, ...]
    right_targets: tuple[str, ...]
    symmetric: bool = False

    def __post_init__(self):
        _text(self, 'name', 'witness', 'left_dimension', 'right_dimension',
              'left_column', 'right_column')
        for field in ('left_targets', 'right_targets'):
            object.__setattr__(self, field, _names(getattr(self, field), field))
            if not getattr(self, field):
                raise ValueError(f"{field} must not be empty")
        if type(self.symmetric) is not bool:
            raise TypeError('symmetric must be boolean')


@dataclass(frozen=True)
class RequiredBridge:
    name: str
    left_dimension: str
    right_dimension: str
    left_targets: tuple[str, ...] = ()
    right_targets: tuple[str, ...] = ()

    def __post_init__(self):
        _text(self, 'name', 'left_dimension', 'right_dimension')
        if self.left_dimension == self.right_dimension:
            raise ValueError('required bridge must connect distinct dimensions')
        for field in ('left_targets', 'right_targets'):
            object.__setattr__(self, field, _names(getattr(self, field), field))


@dataclass(frozen=True)
class CompletenessScope:
    relation: str
    target: str
    mapping: tuple[tuple[str, str], ...]

    def __post_init__(self):
        _text(self, 'relation', 'target')
        if not isinstance(self.mapping, (tuple, list)) or any(not isinstance(p, (tuple, list)) for p in self.mapping):
            raise TypeError('completeness mapping must be an array of pairs')
        pairs = tuple(tuple(pair) for pair in self.mapping)
        if any(len(pair) != 2 or any(not isinstance(v, str) or not v for v in pair)
               for pair in pairs):
            raise TypeError('completeness mapping must contain column-name pairs')
        if len({p[0] for p in pairs}) != len(pairs):
            raise ValueError('duplicate closure mapping column')
        object.__setattr__(self, 'mapping', tuple(sorted(pairs)))


CONTRACT_FIELDS = {
    'compatibility_capabilities': CompatibilityCapability,
    'required_bridges': RequiredBridge,
    'completeness_scopes': CompletenessScope,
}


def decode_contracts(raw):
    """Strict v2 wire decoder; unknown fields cannot be silently discarded."""
    from dataclasses import fields
    result = {}
    for name, cls in CONTRACT_FIELDS.items():
        values = raw.get(name, ())
        if not isinstance(values, (list, tuple)):
            raise TypeError(f'{name} must be an array')
        records = []
        for value in values:
            if not isinstance(value, dict) or set(value) - {f.name for f in fields(cls)}:
                raise ValueError(f'invalid {name} record')
            records.append(cls(**value))
        result[name] = tuple(records)
    return result


@dataclass(frozen=True)
class DerivedCompletenessPolicy:
    """A named, reviewed exact closure rule, including all its prerequisites."""
    name: str
    rule: str
    relation: str
    rule_digest: str

    def __post_init__(self):
        _text(self, 'name', 'rule', 'relation', 'rule_digest')
        if len(self.rule_digest) != 64 or any(c not in '0123456789abcdef' for c in self.rule_digest):
            raise ValueError('derived completeness policy requires a SHA-256 rule identity')


CONTRACT_FIELDS['derived_completeness_policies'] = DerivedCompletenessPolicy
