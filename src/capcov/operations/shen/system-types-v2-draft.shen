\\ DRAFT v2 datatypes for the typed behavior IR. Specification:
\\ docs/ir-specification.md. Each datatype below is one delta the R10 probe
\\ (tests/claim_semantics/test_migration_probe.py) showed the v1 IR cannot
\\ express; nothing else is proposed here.
\\
\\ NOT LOADED BY THE ENGINE. capcov.operations.system.SYSTEM_LIBRARIES names
\\ kernel.shen, system.shen and system-types.shen only; system.py rejects every
\\ tag below that v1 does not have (SYSTEM_TAGS); no evaluator case exists for
\\ any of them. tests/test_ir_specification.py fails if any module names this
\\ file.
\\
\\ NOT TYPECHECKED. Shen could not be built where this draft was written.
\\ "Typecheck draft" is an open gate (docs/ir-specification.md, section 10).
\\ The side-condition functions capsv2.* do not exist yet; each is specified
\\ by the rule id given next to it and lands with its R02 constructor PR.
\\
\\ Reused from system-types.shen without change: caps-expr, caps-pred,
\\ caps-field(s), caps-action(s), caps-named, caps-table(s), caps-column(s),
\\ caps-foreign(s), caps-invariant(s).

\\ Section 4.1. Outcome of one invocation, in the capcov.faults alphabet.
(datatype caps-outcome
  ______________________
  [ok] : caps-outcome;
  R : caps-fail-reason;
  ______________________
  [fail R] : caps-outcome;
  ______________________
  [info] : caps-outcome;)

(datatype caps-fail-reason
  ______________________
  [rejected] : caps-fail-reason;
  L : string;
  ______________________
  [rejected L] : caps-fail-reason;
  ______________________
  [aborted] : caps-fail-reason;)

\\ Section 4.2. Intent identity: stable across retries of one logical request.
\\ The attempt identity is not syntax: it is the invocation id joined with the
\\ step name (section 4.2), assigned by the history.
(datatype caps-intent
  X : caps-expr;
  ______________________
  [intent X] : caps-intent;)

\\ Section 4.3. Delivery contract of an external channel.
(datatype caps-contract
  ______________________
  [at-most-once] : caps-contract;
  ______________________
  [at-least-once] : caps-contract;)

(datatype caps-channel
  Kind : string; C : caps-contract;
  ______________________
  [channel Kind C] : caps-channel;)

\\ Section 4.3. An outbox table: fields "payload" and "state", where state is
\\ one of "pending", "in-flight", "delivered". Rows are keyed by intent id and
\\ created only by [outbox ...] (rule R-OUTBOX-TABLE).
(datatype caps-table-v2
  T : caps-table;
  ______________________
  T : caps-table-v2;
  T : string; Kind : string;
  ______________________
  [outbox-table T Kind] : caps-table-v2;)

\\ Section 4.3. Transactional actions: v1 actions except publish, plus the
\\ outbox record. publish exists only in per-attempt operations (atomic-publish-v1).
(datatype caps-action-v2
  if (not (capsv2.publishes? (capop.value A)))
  A : caps-action;
  ______________________
  A : caps-action-v2;
  T : string; I : caps-intent; V : caps-expr;
  ______________________
  [outbox T I V] : caps-action-v2;
  P : caps-pred; As : caps-actions-v2; Bs : caps-actions-v2;
  ______________________
  [choose P As Bs] : caps-action-v2;
  T : string; P : caps-pred; As : caps-actions-v2;
  ______________________
  [for-each T P As] : caps-action-v2;)

(datatype caps-named-v2
  N : string; A : caps-action-v2;
  ______________________
  [named N A] : caps-named-v2;)

\\ Section 4.3. Steps of an operation with intent identity. A transaction
\\ commits or rejects as a whole. A delivery attempt is external and
\\ non-transactional; its three response arms are all required (rule T-deliver).
(datatype caps-step
  N : string; As : caps-actions-v2;
  ______________________
  [transaction N As] : caps-step;
  N : string; T : string; I : caps-intent; Ok : caps-steps; Fail : caps-steps; Info : caps-steps;
  ______________________
  [deliver N T I [ok Ok] [fail Fail] [info Info]] : caps-step;)

\\ Section 7. The v1 bridge: one transaction of v1 actions, publish included.
(datatype caps-v1-steps
  N : string; As : caps-actions;
  ______________________
  [[transaction N As]] : caps-v1-steps;)

\\ Section 4.2. An operation either has intent identity and v2 steps, or is a
\\ per-attempt v1 command. Rule T-operation: no other combination types.
(datatype caps-operation
  N : string; Args : (list string); Pre : caps-pred; Ss : caps-v1-steps; Post : caps-pred;
  ______________________
  [operation N Args [per-attempt] Pre Ss Post] : caps-operation;
  N : string; Args : (list string); I : caps-intent; Pre : caps-pred; Ss : caps-steps; Post : caps-pred;
  ______________________
  [operation N Args I Pre Ss Post] : caps-operation;)

\\ Section 4.6. The environment re-invokes operation C with the same arguments
\\ after an info or fail [aborted] outcome, at most Max times (rule R-RETRY).
(datatype caps-retry
  C : string; Max : string;
  ______________________
  [retry C Max] : caps-retry;)

\\ Section 4.6. A claim that two operations have disjoint frames (rule R-DISJOINT).
(datatype caps-frame-claim
  A : string; B : string;
  ______________________
  [disjoint A B] : caps-frame-claim;)

\\ Section 7. A named, versioned assumption the model declares. The only name
\\ defined is "atomic-publish-v1"; any other name is rejected (rule R-ASSUME).
(datatype caps-assumption
  Name : string;
  ______________________
  [assume Name] : caps-assumption;)

(datatype caps-system-v2-shape
  N : string; As : caps-assumptions; Ts : caps-tables-v2; Chs : caps-channels;
  Os : caps-operations; Rs : caps-retries; Fs : caps-frame-claims; Ps : caps-invariants;
  ______________________
  [system-v2 N As Ts Chs Os Rs Fs Ps] : caps-system-v2-shape;)

\\ capsv2.scoped? is caps.scoped? lifted to v2 plus the rules R-INTENT-SCOPE,
\\ R-OUTBOX-TABLE, R-CHANNEL, R-NAMES, R-LATE-REJECT, R-RETRY, R-DISJOINT,
\\ R-ASSUME.
(datatype caps-system-v2
  if (capsv2.scoped? (capop.value M))
  M : caps-system-v2-shape;
  ______________________
  M : caps-system-v2;)

\\ Section 4.2. Runtime effect records. Values are strings, as in v1 states.
(datatype caps-logical-effect
  T : string; K : string; Fs : caps-values;
  ______________________
  [create T K Fs] : caps-logical-effect;
  T : string; K : string; F : string; V : string;
  ______________________
  [put T K F V] : caps-logical-effect;
  T : string; K : string;
  ______________________
  [delete T K] : caps-logical-effect;
  T : string; K : string; V : string;
  ______________________
  [recorded T K V] : caps-logical-effect;
  Kind : string; V : string;
  ______________________
  [delivered Kind V] : caps-logical-effect;
  Kind : string; V : string;
  ______________________
  [emit Kind V] : caps-logical-effect;)

(datatype caps-effect
  I : string; A : string; L : caps-logical-effect;
  ______________________
  [effect I A L] : caps-effect;)

(datatype caps-value
  F : string; V : string;
  ______________________
  [F V] : caps-value;)

\\ Section 4.4. Histories. Every invocation not completed before [close] is
\\ info; an info invocation stays open until [close] (rule R-HISTORY).
(datatype caps-event
  ______________________
  [open] : caps-event;
  Inv : string; Op : string; Args : caps-values;
  ______________________
  [invoke Inv Op Args] : caps-event;
  Inv : string; O : caps-outcome;
  ______________________
  [complete Inv O] : caps-event;
  Ob : caps-observation;
  ______________________
  [read Ob] : caps-event;
  ______________________
  [close] : caps-event;)

(datatype caps-history
  if (capsv2.well-formed-history? (capop.value H))
  Es : caps-events;
  ______________________
  [history Es] : caps-history;)

\\ Section 4.5. Partial observations. A cut names the stores read, whether a
\\ barrier makes the reads mutually consistent, and whether the external
\\ channels attest that no accepted attempt is still unapplied.
(datatype caps-observation
  C : caps-cut; Rows : caps-rows; J : caps-journal;
  ______________________
  [observation C Rows J] : caps-observation;)

(datatype caps-cut
  Stores : (list string); B : caps-barrier; D : caps-drain;
  ______________________
  [cut Stores B D] : caps-cut;)

(datatype caps-barrier
  B : string;
  ______________________
  [barrier B] : caps-barrier;
  ______________________
  [no-barrier] : caps-barrier;)

(datatype caps-drain
  ______________________
  [drained] : caps-drain;
  ______________________
  [not-drained] : caps-drain;)

(datatype caps-row
  T : string; K : string; Fs : caps-values;
  ______________________
  [row T K Fs] : caps-row;)

\\ A journal declares the sequence range it covers. Entries carry their
\\ sequence number; [gap From To] says the range was not observed.
(datatype caps-journal
  From : string; To : string; Ps : caps-journal-parts;
  ______________________
  [journal From To Ps] : caps-journal;)

(datatype caps-journal-part
  Seq : string; E : caps-effect;
  ______________________
  [entry Seq E] : caps-journal-part;
  From : string; To : string;
  ______________________
  [gap From To] : caps-journal-part;)

(datatype caps-tables-v2
  ______________________
  [] : caps-tables-v2;
  X : caps-table-v2; Xs : caps-tables-v2;
  ______________________
  (cons X Xs) : caps-tables-v2;)

(datatype caps-assumptions
  ______________________
  [] : caps-assumptions;
  X : caps-assumption; Xs : caps-assumptions;
  ______________________
  (cons X Xs) : caps-assumptions;)

(datatype caps-channels
  ______________________
  [] : caps-channels;
  X : caps-channel; Xs : caps-channels;
  ______________________
  (cons X Xs) : caps-channels;)

(datatype caps-actions-v2
  ______________________
  [] : caps-actions-v2;
  X : caps-named-v2; Xs : caps-actions-v2;
  ______________________
  (cons X Xs) : caps-actions-v2;)

(datatype caps-steps
  ______________________
  [] : caps-steps;
  X : caps-step; Xs : caps-steps;
  ______________________
  (cons X Xs) : caps-steps;)

(datatype caps-operations
  ______________________
  [] : caps-operations;
  X : caps-operation; Xs : caps-operations;
  ______________________
  (cons X Xs) : caps-operations;)

(datatype caps-retries
  ______________________
  [] : caps-retries;
  X : caps-retry; Xs : caps-retries;
  ______________________
  (cons X Xs) : caps-retries;)

(datatype caps-frame-claims
  ______________________
  [] : caps-frame-claims;
  X : caps-frame-claim; Xs : caps-frame-claims;
  ______________________
  (cons X Xs) : caps-frame-claims;)

(datatype caps-values
  ______________________
  [] : caps-values;
  X : caps-value; Xs : caps-values;
  ______________________
  (cons X Xs) : caps-values;)

(datatype caps-events
  ______________________
  [] : caps-events;
  X : caps-event; Xs : caps-events;
  ______________________
  (cons X Xs) : caps-events;)

(datatype caps-rows
  ______________________
  [] : caps-rows;
  X : caps-row; Xs : caps-rows;
  ______________________
  (cons X Xs) : caps-rows;)

(datatype caps-journal-parts
  ______________________
  [] : caps-journal-parts;
  X : caps-journal-part; Xs : caps-journal-parts;
  ______________________
  (cons X Xs) : caps-journal-parts;)
