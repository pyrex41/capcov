# Architecture critique: incorporated decisions and remaining work

The review supplied on October 17 distinguishes execution evidence, formal
judgments and implementation trust. The completion milestone adopts that
separation explicitly. It does not treat the review's proposed ELF/x86-64 slice
or LuaJIT plugin runtime as an accepted implementation requirement.

| Review point | Treatment in this branch's new loop work |
| --- | --- |
| Python owns IR, digests and transport | Retained. Loop WP, capture substitution and obligation generation are explicitly trusted Python transformations, identified separately from proof kernels. |
| Sequent datatypes are narrower than “typed rules” suggests | Added actual Shen datatypes for completion formulas, contexts and judgments. The claim authorities and semantic checker functions remain untyped. No hand-written shape test is described as a Shen type proof. |
| Shen is invoked per request | Unchanged. Neither loop checking nor completion adds a persistent process or incremental evaluator. Model validation now binds the model once per invocation rather than repeating its text for every annotation. |
| Confidence has separate semantic and operational dimensions | Retained. Open obligations, operational errors, checked model proofs, source freshness and observed conformance are not collapsed into a confidence score. |
| Soufflé supplies relation closure with differential checking | No changes to that subsystem in this milestone, and no claim that new Soufflé validation was performed. Completion uses the Shen proof path. |
| Reuse content identities, manifests and marker transport | Extended existing identities and native runner. New code and datatype resources are hashed and packaged; model/source binding is preserved. |
| Binary fact schema and disassembly mapping were guesses | Not promoted into implementation assumptions or proved facts. No ELF adapter or binary-analysis fact schema has been added. |
| LuaJIT is absent | No LuaJIT runtime/plugin architecture has been introduced. |

The new completion checker typechecks the *judgment's structure*, validates the
mutation frame and checks proof derivations. This does not establish that the
Python transformations implement the interpreter semantics, nor that an
application implements the model. Those are separate refinement obligations.

Further work prompted by the critique:

1. Extend genuine typed judgments into claim elaboration, with explicit producer,
   completeness and compatibility witnesses. This has not been implemented by
   adding the completion datatypes.
2. Mechanize or differentially validate the compiler/interpreter boundary beyond
   the present mutation and conformance tests.
3. Evaluate persistent Shen sessions with explicit environment identity and
   isolation; avoid claiming cache reuse is incremental evaluation.
4. Treat a binary-analysis framework as a separate design decision. It would need
   a validated fact schema, architecture-specific extraction, explicit unknowns,
   and a checked mapping from observations to claims before an ELF first slice.

The reviewer's reported native test run and inability to run Soufflé describe
their environment. They are not substituted for the validation performed for
this milestone.
