# Direct comparison with Reversa

The reference is [Reversa v1](https://arxiv.org/html/2605.18684v1), May 18, 2026.
Its central contribution is source-traceable operational documentation produced
through specialized recovery/review roles, with explicit confidence and gaps.
The exploratory COBOL-to-Go case reported 517 claims, 53 Gherkin scenarios and
10 registered project gaps; final parity validation and cutover were unfinished.
Those numbers measure the reported case, not accuracy or production readiness.

This comparison concerns the paper's documented method and results. It does not
infer that later Reversa releases lack executable migration tooling. The new
capcov importer is a reviewed JSON exchange boundary, not a plugin that executes
Reversa agents or parses every Reversa artifact automatically.

| Concern | Reversa emphasis | This branch's implemented contribution |
| --- | --- | --- |
| Recovery | Specialized roles produce linked specifications | Source-linked claim/gap import into a versioned Behavior registry |
| Confidence | Explicit uncertainty and unresolved gaps | Confidence retained; static extraction cannot satisfy an execution obligation |
| Unit of organization | Operational specifications for reconstruction | Behavior links entry, target, legacy model, stores, access paths and obligations |
| Target | Specifications guide reconstruction | Shen-admitted executable Step handlers and worker-only external delivery |
| Data | Recover system knowledge needed by specifications | Four mandatory store-contract layers and explicit writer/bypass records |
| Validation | Parity scenarios guide validation | Executed checks with receipts, exact decision-aware comparison, effect replay and stateful tests |
| Change impact | Traceability supports maintenance | Hash-bound dependency closure and export to capcov's existing Souffle rules |
| Protocol | Migration concerns require validation | Integrated ShenCheck/Vör model export, generated TLA+ and mandatory defect controls |
| Release judgment | Gaps require resolution | Scoped gate refuses stale evidence, missing obligations and representation ambiguity |

The integration point is evidence, not prose generation. A recovery agent can
identify that publication invokes an observer, cite the relevant artifact and
mark confidence. A reviewer maps it to an access path and an obligation. A trace
or fixture then checks whether the effect actually occurs through that path.
Only that execution supplies execution evidence. Changing the cited source or
its contract invalidates dependent qualification.

For example, a recovered statement that every save updates an identifier is too
broad if it came from one ORM hook. Record the path on which the hook runs and the
raw-SQL path on which it does not. The synthetic publication fixture explicitly
implements the identifier update in its transactional adapter. Its mixed-writer
test assumes the competing writer increments the version. That assumption must
be checked for a real legacy backend before using the result for cutover.

The synthesized workflow keeps recovery roles useful while making their outputs
reviewable inputs to executable obligations. It does not require a full narrative
specification before the first target behavior exists. Recover breadth quickly;
complete one behavior vertically; turn each counterexample into a source/model
correction, a target fix, a narrowly approved change or an explicit gap.

Limits are symmetrical. Better source explanations do not establish parity;
passing the new example does not establish that an arbitrary recovery is correct.
This branch has no automatic legacy-to-Step compiler, complete PHP hook inference,
source/model refinement proof or unattended agent orchestration. Those remain
separate engineering tasks, with their results subject to the same evidence gate.
