"""Behavior registry and qualification orchestration; model semantics stay in Shen."""

from capcov.operations import OperationError
from .progress import build_progress


class BehaviorError(OperationError):
    """Invalid, stale or unsupported behavior evidence."""
