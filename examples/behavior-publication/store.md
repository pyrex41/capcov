# Synthetic publication store contract

## Physical

SQLite tables issue, permission, request, outbox and a fake provider. Composite
tenant keys. BEGIN IMMEDIATE serializes the conditional publication transaction.
The fake provider table represents a separate service even though this test
stores its data in SQLite. Provider delivery and local settlement are separate.

## Representation

N/A means an unassigned identifier; ISSUE-<id> is the assigned toy encoding.
Other encodings return ambiguous and block publication. This is a synthetic
meaning, not a classification of the production application's sentinel values.
Domain numbers cross the Step wire as validated decimal strings.

## Access

The target adapter uses explicit tenant predicates and increments issue.version.
An external writer must increment the same version or participate in a stronger
ownership protocol. Raw writes that ignore this contract are unsupported and
must block real mixed-writer cutover. No ORM hook is assumed to run on raw SQL.

## Domain

Publication changes a draft and records a request result and pending intent in
one transaction. Authorization is rechecked inside that transaction. A repeated
tenant/principal/request with identical payload reuses its result. Payload
changes conflict. The provider deduplicates by tenant/intent and rejects changed
payloads. Unknown delivery leaves a pending intent; the worker may retry under
that provider assumption. No global exactly-once claim is made.
