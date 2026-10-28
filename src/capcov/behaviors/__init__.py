"""Behavior registry and qualification orchestration; model semantics stay in Shen."""

from capcov.operations import OperationError


class BehaviorError(OperationError):
    """Invalid, stale or unsupported behavior evidence."""
