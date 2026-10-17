"""Snapshot partition induction for row-local, domain-preserving transforms.

Selected = Processed ++ Remaining. Processed rows satisfy Q; Remaining rows
retain their captured fields; unselected rows satisfy Q by the entry obligation.
Updating only the current captured key preserves that partition invariant.
"""

from .compiler import Unresolved, _instance, wp, formula


def row_local(node):
    if not isinstance(node, list) or not node:
        return True
    return node[0] in (
        "yes",
        "no",
        "literal",
        "argument",
        "row-key",
        "row-field",
        "equal",
        "less-than",
        "negate",
        "both",
        "either",
        "int-add",
        "int-sub",
    ) and all(row_local(x) for x in node[1:] if isinstance(x, list))


def local_actions(table, actions):
    for _, _, action in actions:
        tag = action[0]
        if tag == "update":
            if action[1] != table or action[2] != ["row-key"]:
                return False
        elif tag == "choose":
            if not local_actions(table, action[2]) or not local_actions(
                table, action[3]
            ):
                return False
        elif tag not in ("publish", "require"):
            return False
    return True


def snapshot_reads(node, table, key, fields):
    """Only at head-of-Remaining entry: live head fields equal captured fields."""
    if not isinstance(node, list) or not node:
        return node
    if node[0] == "before":
        return node
    if len(node) == 4 and node[0] == "lookup" and node[1] == table and node[2] == key:
        return ["argument", fields[node[3]]]
    return [snapshot_reads(x, table, key, fields) for x in node]


def derive(action, predicate, names, captured):
    _, table, selector, actions = action
    if not row_local(selector) or not row_local(predicate):
        raise Unresolved("completion requires row-local selector and result predicate")
    if not local_actions(table, actions):
        raise Unresolved(
            "completion frame requires updates only to the current captured key; domain changes and nested loops need a stronger rule"
        )
    key = ["argument", names["key"]]
    target = _instance(predicate, table, key)
    weakest = wp(captured(actions, names), target)
    weakest = snapshot_reads(weakest, table, key, names["fields"])
    coverage = (
        ["yes"]
        if selector == ["yes"] or predicate == ["yes"]
        else ["every-row", table, ["either", selector, predicate]]
    )
    return {
        "rule": "snapshot-partition",
        "table": table,
        "body": actions,
        "selector": selector,
        "predicate": predicate,
        "coverage": coverage,
        "established": ["every-row", table, predicate],
        "left": [formula(captured(selector, names))],
        "right": [formula(weakest)],
    }
