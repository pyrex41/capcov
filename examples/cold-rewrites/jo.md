# jo: C → Go

[Upstream](https://github.com/jpmens/jo) · [Shared freeze, repair arms and scoring protocol](README.md)

**Status:** prompt stub; no release pinned or result claimed.

**Implementer brief (public):** Build a standalone Go CLI for the pinned jo invocation modes in the contract. Pass argv directly (no shell expansion). Specify stdin, working directory, locale and exit semantics. Do not wrap jo.

**Capcov evaluator prompt (private):** Model one process invocation as a vector. Observe exit code, stderr presence, and parsed stdout JSON including types; keep raw stdout for diagnosis. Treat object order as irrelevant but array order as significant. Score byte-level formatting only in a separately declared contract.

**Campaign design prompt (private):** Plan families for type inference, repeated fields, array mode, and values arriving on stdin. Include successful and rejected invocations verified against the pinned release. Shrink by deleting arguments or shortening a value while preserving the same difference. Apply the shared split and budget rules before candidate generation.
