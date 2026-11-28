# LMDB: specialize a transaction program

[Upstream](https://github.com/LMDB/lmdb) · [Projection and timing protocol](database-projection.md) · [Capcov role prompts](README.md)

**Status:** design stub; no performance or compatibility claim.

**Implementer prompt:** Build a Rust ordered key/value engine for a bounded single-writer transaction DSL (get, put, delete, commit/abort) with bytewise keys and named result slots. Start with one database and sequential clients. Use real LMDB transactions as oracle. State whether clean close/reopen is supported; crash consistency, cross-process readers, and file-format compatibility are separate obligations. Do not wrap LMDB in the target and call that a storage-engine rewrite.

**Binding-time prompt:** LMDB is not a query interpreter: introduce the transaction DSL explicitly. Static: transaction operation sequence, result-slot wiring, key/value codecs. Dynamic: key/value bytes, reads, branch outcomes and commit state. Specialize the transaction interpreter over the same target storage backend. The projection optimizes transaction dispatch; it does not derive a B-tree or optimize arbitrary disk I/O.

**Evaluator prompt (private):** Check abort after overwrite/delete, missing versus empty values, repeated keys, and committed state from a subsequent reader. Benchmark read-heavy and write-heavy transactions separately at matched sync settings. Separate warmed page-cache runs from reopen (reopen is not a cold OS cache). Report transactions/s, tail latency and bytes per transaction. If storage or fsync dominates and dispatch savings disappear, report it rather than weakening durability.
