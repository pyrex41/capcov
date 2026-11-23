# Fork baseline

Use `pyrex41/capcov:main` for integrated development. Upstream `millstonehq/capcov:main` is not the fork integration target. Historical branch names are provenance, not prerequisite checkouts.

- The [Behavior system](unified-behavior-system.md) owns application-level claims and obligations. [Environment recovery](environment-recovery.md) proposes graph-relative effects; [breadth-first progress](behavior-progress.md) tracks product scope. Neither substitutes for execution evidence.
- The [reasoning workbench](reasoning-workbench.md) and [runtime policy](shen-runtime-choice.md) supply bounded search, checks, and replay. [Behavioral learning](behavioral-learning.md) and [synthesis](behavioral-synthesis.md) propose and challenge hypotheses, not authoritative requirements.
- [Boundary learning](../experiments/boundary-learning/README.md), [LLM induction](../experiments/semantic-learning/llm/README.md), and the [snapshot rewrite](../experiments/rewrite-snapshot/README.md) are experiments with distinct observation contracts, not production acceptance gates.

## Consolidation decisions

Base `6b347f5` already included upstream main, the typed/specification roadmap, fleet fixes, parallel skip checking, runtime-choice work, and Scheme updates. Incorporated the fork's validation fix (`64c837f`), progress (`5f8ab2e`), environment recovery (`3cf3a63`), boundary experiments (`eff7e75`), learning/synthesis (`e8b0033`) and replay experiments (`4802cce`). The older upstream-facing branches were compared by content, not blindly merged: retained boundary docs from `cf9ae3d`, rule-miner discoverability from `6ee7396`, and the reason subcommand help from `be9e414`. Kept main's unittest `getDescription` and worker synchronization rather than replacing them with the portable PR's hand-built failure description and older test. Earlier validation reports identify their original revisions; they do not certify the integrated tree.
