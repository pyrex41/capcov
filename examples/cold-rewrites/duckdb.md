# DuckDB: specialize an analytical query plan

[Upstream](https://github.com/duckdb/duckdb) · [Projection and timing protocol](database-projection.md) · [Capcov role prompts](README.md)

**Status:** design stub; no performance or compatibility claim.

**Implementer prompt:** Build a Rust columnar executor for a typed relational IR: scan, nullable integer filter, project and grouped COUNT/SUM. Start single-threaded, with integer ranges and accumulator widths explicitly bounded to match the reference. Translate each IR program into equivalent DuckDB SQL for the oracle; this is not a rewrite of DuckDB's optimizer, SQL parser or file format.

**Binding-time prompt:** Static: physical plan, column slots, nullability and types. Dynamic: bound predicate values, batch lengths, validity masks, group keys and column buffers. Stage the interpreter into a residual native kernel; keep the same batching, aggregation implementation and layout in the generic baseline so a different hash table doesn't masquerade as specialization.

**Evaluator prompt (private):** Vary selectivity, NULL density, empty/all-NULL groups, batch tails, repeated keys and group cardinality. Compare typed bags with multiplicity unless order is explicitly contracted. Separate prepared DuckDB end-to-end timings from internal kernel comparisons; measure rows/s and memory at several working-set sizes. First milestone: one generate-once kernel handles unseen parameter values and datasets; then repeat for previously unseen plan shapes.
