"""A checked finite evaluation basis is distinct from external-world closure.

The producer remains responsible for admitting completeness evidence. This
module checks the computation over the admitted input, not that trust decision.
"""
from dataclasses import dataclass
from .ir import digest
from .validation import assert_valid
from .evaluator import evaluate
from .static.certificate import normalize_relations, rules_digest


@dataclass(frozen=True)
class EvaluationBasis:
    bundle_digest: str
    rules_digest: str
    closure_digest: str
    relations: tuple


def evaluate_basis(bundle):
    assert_valid(bundle)
    result = evaluate(bundle)
    if result.status.value != 'complete':
        raise ValueError(f'evaluation did not complete: {result.status}')
    return EvaluationBasis(digest(bundle), rules_digest(bundle),
                           digest(normalize_relations(result.relations)), result.relations)


def check_basis(bundle, basis):
    """Recompute, so neither a purported status nor a supplied digest is trusted."""
    if not isinstance(basis, EvaluationBasis):
        return False
    try:
        return basis == evaluate_basis(bundle)
    except (ValueError, TypeError):
        return False
