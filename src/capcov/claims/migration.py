"""Explicit artifact conversion. Certificates are never inputs to conversion."""
from dataclasses import dataclass, replace
from .ir import Bundle, digest
from .validation import assert_valid


@dataclass(frozen=True)
class Conversion:
    bundle: Bundle
    old_digest: str
    new_digest: str
    from_version: int = 1
    to_version: int = 2


def convert_v1(bundle, *, compatibility_capabilities, completeness_scopes, required_bridges=(), derived_completeness_policies=()):
    if bundle.schema_version != 1:
        raise ValueError('conversion requires an original schema-v1 bundle')
    assert_valid(bundle)
    converted = replace(bundle, schema_version=2,
        relations=tuple(replace(r, compatibility_targets=(), compatibility_context_indices=()) for r in bundle.relations),
        compatibility_capabilities=tuple(compatibility_capabilities),
        completeness_scopes=tuple(completeness_scopes), required_bridges=tuple(required_bridges),
        derived_completeness_policies=tuple(derived_completeness_policies))
    assert_valid(converted)
    return Conversion(converted, digest(bundle), digest(converted))
