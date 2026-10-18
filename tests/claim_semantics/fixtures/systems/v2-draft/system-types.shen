\\ R02 DRAFT OVERLAY: additions to the v1 grammar,
\\ src/capcov/operations/shen/system-types.shen, loaded after it.
\\ Specification: docs/ir-specification.md.
\\
\\ Additive only. Every datatype below has a new name; a rule that extends a
\\ v1 type concludes that type (as caps-expr-arithmetic does in v1). No v1
\\ datatype is redefined, so every v1 model types as before. Each block names
\\ the R02 PR that lands it (section 8).
\\
\\ Not loaded by the engine and not packaged: it lives under tests/. Typing is
\\ structural only; the R-* side conditions of section 4.7 are specified in
\\ the doc and land with their PR. tests.test_ir_specification.
\\ DraftTypecheckTest (shen family) loads kernel.shen, system-types.shen and
\\ this file under (tc +) and typechecks the fixtures beside it.

\\ PR 1. Outcome of one invocation, in the capcov.faults alphabet.
(datatype caps-outcome
  ______________________
  [ok] : caps-outcome;
  R : caps-fail-reason;
  ______________________
  [fail R] : caps-outcome;
  ______________________
  [info] : caps-outcome;)

(datatype caps-fail-reason
  L : string;
  ______________________
  [rejected L] : caps-fail-reason;
  ______________________
  [aborted] : caps-fail-reason;)

\\ PR 1. Effect records: intent id, attempt id, logical effect. The logical
\\ effects are v1's runtime effects (system.py:100-104), now typed.
(datatype caps-effect
  I : string; A : string; L : caps-logical-effect;
  ______________________
  [effect I A L] : caps-effect;)

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
  Kind : string; V : string;
  ______________________
  [emit Kind V] : caps-logical-effect;)

(datatype caps-value
  F : string; V : string;
  ______________________
  [F V] : caps-value;)

\\ PR 1. A system that names its assumptions (strings, section 7).
(datatype caps-system-assuming
  N : string; As : (list string); Ts : caps-tables; Cs : caps-commands; Ps : caps-invariants;
  ______________________
  [system N As Ts Cs Ps] : caps-system-shape;)

\\ PR 2. Intent identity, stable across retries of one logical request.
(datatype caps-intent
  X : caps-expr;
  ______________________
  [intent X] : caps-intent;)

\\ PR 2. A transactional outbox record, a v1 action.
(datatype caps-action-outbox
  T : string; I : caps-intent; V : caps-expr;
  ______________________
  [outbox T I V] : caps-action;)

\\ PR 2. A channel declares its delivery contract and its outbox table T
\\ (fields "payload", "state"), so it is a table declaration.
(datatype caps-contract
  ______________________
  [at-most-once] : caps-contract;
  ______________________
  [at-least-once] : caps-contract;)

(datatype caps-table-channel
  Kind : string; C : caps-contract; T : string;
  ______________________
  [channel Kind C T] : caps-table;)

\\ PR 2. Steps of an operation. PR 2 types all three response arms, so an
\\ omitted on-info arm never types; on-info becomes reachable in PR 3.
(datatype caps-step
  N : string; As : caps-actions;
  ______________________
  [transaction N As] : caps-step;
  N : string; T : string; I : caps-intent; Ok : caps-steps; Fail : caps-steps; Info : caps-steps;
  ______________________
  [deliver N T I [on-ok Ok] [on-fail Fail] [on-info Info]] : caps-step;)

(datatype caps-steps
  ______________________
  [] : caps-steps;
  X : caps-step; Xs : caps-steps;
  ______________________
  (cons X Xs) : caps-steps;)

\\ PR 2. An operation has intent identity. A v1 command is the sugar for an
\\ operation without one: one transaction, intent = invocation id.
(datatype caps-operation
  N : string; Args : (list string); I : caps-intent; Pre : caps-pred; Ss : caps-steps; Post : caps-pred;
  ______________________
  [operation N Args I Pre Ss Post] : caps-operation;)

(datatype caps-commands-operation
  X : caps-operation; Xs : caps-commands;
  ______________________
  (cons X Xs) : caps-commands;)

\\ PR 4. Histories. Open and close markers; invocations and completions.
(datatype caps-event
  ______________________
  [open] : caps-event;
  Inv : string; Op : string; Args : caps-values;
  ______________________
  [invoke Inv Op Args] : caps-event;
  Inv : string; O : caps-outcome;
  ______________________
  [complete Inv O] : caps-event;
  ______________________
  [close] : caps-event;)

(datatype caps-history
  Es : caps-events;
  ______________________
  [history Es] : caps-history;)

\\ PR 5. A read of several stores. B: the reads form one cut (barrier).
\\ Per store, D: the store is drained (no pending write or landing).
(datatype caps-event-observation
  B : boolean; Rs : caps-reads;
  ______________________
  [observation B Rs] : caps-event;)

(datatype caps-read
  T : string; D : boolean; Rows : caps-rows;
  ______________________
  [rows T D Rows] : caps-read;
  S : string; D : boolean; From : string; To : string; Ps : caps-journal-parts;
  ______________________
  [journal S D From To Ps] : caps-read;)

(datatype caps-row
  K : string; Fs : caps-values;
  ______________________
  [row K Fs] : caps-row;)

(datatype caps-journal-part
  Seq : string; E : caps-effect;
  ______________________
  [entry Seq E] : caps-journal-part;
  From : string; To : string;
  ______________________
  [gap From To] : caps-journal-part;)

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

(datatype caps-reads
  ______________________
  [] : caps-reads;
  X : caps-read; Xs : caps-reads;
  ______________________
  (cons X Xs) : caps-reads;)

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
