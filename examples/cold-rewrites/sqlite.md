# SQLite: specialize the query VM

[Upstream](https://github.com/sqlite/sqlite) · [Projection and timing protocol](database-projection.md) · [Capcov role prompts](README.md)

For WAL capture, distributed durability and failover rather than query execution, use the separate [SQLite replication protocol brief](sqlite-replication.md).

**Status:** design stub; no performance or compatibility claim.

**Implementer prompt:** Build a C or Rust interpreter for an explicit allowlist of read-only VDBE opcodes from one pinned SQLite build. Begin with scalar parameterized integer SELECT/CASE programs without table access. Extract the opcode listing with EXPLAIN, execute the original SQL through that same build for the oracle, and reject programs outside the allowlist. VDBE is version-specific, not a stable portable IR. Table scans are a later milestone, not a silent dependency on SQLite to run residual code.

**Binding-time prompt:** Static: instruction sequence, operand locations, constants and control-flow targets. Dynamic: bound values and NULLs, registers and branch outcomes. Specialize dispatch and constant operands; preserve SQL type tags and three-valued branches. Do not cache a previous binding as a program constant.

**Evaluator prompt (private):** Compare typed rows, row order where specified, and error outcomes across new bindings and fresh opcode/control-flow shapes. Freeze treatment of overflow and coercions or explicitly exclude them. Benchmark repeated bind/step/reset on one prepared statement versus generic VM and residual invocation, with separate compilation and host-call overhead. Add a many-distinct-statements workload to challenge amortization.
