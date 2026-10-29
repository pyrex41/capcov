# Breadth-first product progress

CapCov owns persistent product progress as part of its existing behaviors workflow.
This is **reported, not verified** accounting, not another evaluator. It neither
executes code nor replaces execution, comparator, qualification or cutover ledgers.
Evidence references are claims, not adjudicated facts. A passing test count, route
count, harness improvement or new tool is never automatically a product capability.
Authentication, authorization, tenant-isolation and data-integrity baselines must **never** be
sacrificed for breadth. A baseline/security fix can explicitly unblock breadth;
ordinary depth polishing waits until every candidate has complete retained breadth.
Implemented claims must reference the real entry, business logic, intended
persistence/effects path and focused tests. Stubs, route-only presence and
fixture-only implementations do not count. CapCov validates reference presence,
not those references' truth; reviewers and existing qualification remain responsible.

## API and persistence

```python
from capcov.behaviors.progress import build_progress
report = build_progress(plan, previous=None)  # stdlib only; invalid inputs raise ValueError
```

```sh
PYTHONPATH=src python -m capcov.behaviors progress --plan plan.json --out progress.json
PYTHONPATH=src python -m capcov.behaviors progress --plan plan.json --out next.json --previous progress.json
```

No `--registry` is needed. The command exits 0 when it writes a valid report, even
when progress is incomplete, and 2 for invalid input/I/O errors. The caller owns
the plan and persists each output; no daemon or hidden state exists. `--previous`
accepts a prior **report**, not a plan; its embedded plan is recomputed instead of
trusting editable historical totals. Use distinct output files to retain history.
The API does not mutate either input. Inputs and outputs use the existing behaviors
convention: the version discriminator is **`format`**, not `schema`.

## Input: `capcov-progress-plan-v1`

```json
{
  "format": "capcov-progress-plan-v1",
  "unit_namespace": "example/retained-product-capabilities",
  "candidates": [
    {"id": "one", "source_pin": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
    {"id": "two", "source_pin": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},
    {"id": "three", "source_pin": "cccccccccccccccccccccccccccccccccccccccc"}
  ],
  "units": [
    {"id": "create", "label": "Create workspace", "area": "workspaces", "disposition": "retain", "scope_basis": "Reviewed product requirement"},
    {"id": "old-create", "label": "Old create routes", "area": "workspaces", "disposition": "replace", "replacement_id": "create", "scope_basis": "Explicit replacement by create"},
    {"id": "export", "label": "Export workspace", "area": "workspaces", "disposition": "unresolved", "scope_basis": ""}
  ],
  "depth_dimensions": ["authorization", "data-integrity", "failure-recovery", "usability", "performance"],
  "targets": {"breadth": 100, "depth": 80},
  "cells": [
    {"unit": "create", "candidate": "one", "source_pin": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "stage": "implemented", "owner": "workspace-team", "blocker": null, "evidence": ["receipts/create.json"], "depth": {"authorization": "pass", "data-integrity": "pass"}}
  ]
}
```

Required top-level fields: `format`, nonempty `unit_namespace`, nonempty
`candidates`, `units`, `cells`, nonempty unique `depth_dimensions`.
`targets` is optional (default breadth 100, depth 80); supplied targets require
both numeric percentage fields in [0,100]. These are policy, not achieved values.

- Each candidate requires a unique nonempty `id` and full 40-hex `source_pin`.
  Candidate count is generic; every supplied candidate is always reported.
- Each unit requires unique `id`, nonempty `label`, nonempty `area`, `disposition`
  (`retain`, `replace`, `exclude`, `unresolved`) and string `scope_basis`.
  All resolved dispositions require nonblank basis. Exclusions stay visible.
- `replace` requires `replacement_id` pointing **directly to an existing retain
  unit**. The retained target represents the replacement capability and counts
  once; aliases do not add denominator entries or confer evidence on that target.
  Chains, cycles, dangling references and replacement IDs on other dispositions
  are rejected. Inventory importers must explicitly supply replacement targets.
- Each cell requires existing `unit` and `candidate`, full `source_pin`, `stage`
  (`unknown`, `missing`, `partial`, `implemented`), `owner` and `blocker` (nonblank
  string or null), `evidence` (array of nonblank reference strings), and `depth`
  (object mapping declared dimension names to `unknown`, `pass`, `fail`).
  Implemented requires at least one reference. Duplicate cells, unknown IDs,
  dimensions and statuses are rejected. Missing depth entries become unknown.
- Optional cell `depth_unblock_reason` is an object with `kind` (`security` or
  `critical`) and nonblank `reason`. It permits only that cell's pending depth to
  enter the queue before all-product breadth completion; no blanket polish bypass.

Use one explicit namespace/granularity per plan: obligations, route variants and
capability nodes are different inventories, not numbers to add into one total.
CapCov cannot adjudicate the input taxonomy; scope review remains the caller's job.

## Output: `capcov-progress-v1`

- `plan`: saved original input for reproducible historical comparison.
- `candidates`, `units`, `depth_dimensions`, `targets`, `unit_namespace`: explicit
  inventory and policy, with no averaged candidate score.
- `cells`: every unit × candidate, including exclusions, aliases and unresolved
  scope. Omitted cells become unknown with null owner/blocker and empty evidence.
  Each has `eligible`, `capability_unit`, `omitted`, `stale`, `unknown_reason`,
  `reported_stage`, `reported_depth`, and `evidence_status: reported-not-verified`.
  `stage` and `depth` are effective accounting values. Pin mismatch makes both
  unknown and receives **zero** credit; historical reported claims remain visible.
- `summary[candidate]` and `by_area[candidate][area]`: eligible/implemented counts,
  stage counts, excluded/alias/unresolved counts, unowned IDs, blockers, stale IDs,
  `reported_breadth_percent`, `inventory_breadth_floor_percent`,
  `depth_passed`, `depth_denominator`, `reported_depth_percent`,
  `breadth_complete`, `targets_met`. Empty denominators yield null, never 100.
- `breadth_complete`: all candidates have all retained units implemented and no
  unresolved scope. `targets_met`: all candidates meet policy, scope is resolved,
  and no historical scope/inventory review is required. A candidate's local policy
  result is separate from this global review gate.
- `delta`: `cell_movements`, `regressions`, `inventory_changes`, `scope_changes`,
  `pin_changes`, `policy_changes`, `review_issues`, plus `denominators` on historical
  comparisons. Movements have unit/candidate and field-wise before/after values.
  Regressions include stage loss and pass-to-fail/unknown dimension transitions;
  they are never netted against improvements elsewhere. Unit/candidate removals,
  scope edits (including exclusions, aliases, labels and areas), namespace changes
  policy/dimension changes and source-pin changes set `review_required` with exact issue references.
  Source-pin changes are separately listed and stale cell claims lose credit.
- `work_queue` and `next_work`: product breadth gaps (missing, unknown, partial)
  interleaved round-robin across candidates, then unresolved scope decisions, then
  depth work **only when all candidates' breadth is complete**. Explicit
  security/critical unblock tasks are the only early-depth exception. Tasks carry
  area, owner, blocker and reason; no tooling/harness work is invented as a cell.

Reported breadth = implemented retained capability units / retained capability
units. A retained replacement target counts once, regardless of old route aliases.
Inventory breadth floor = implemented / (retained + unresolved). **Do not present
100% retained-subset breadth as 100% product breadth while unresolved scope exists**;
use the floor and completion flags. Depth = passed dimensions / (all retained units
× all declared dimensions), including missing units, never only the covered subset.
Percentages are rounded to six decimals. No positive delta is inferred from a
shrinking denominator; losses and scope changes require explicit review. To accept
a reviewed new baseline, persist the reviewed plan/report and compare the next run
against it; CapCov never edits old evidence or silently re-pins a candidate.
