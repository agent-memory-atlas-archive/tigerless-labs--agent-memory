# Design

- [Batch write boundaries](batch-write-boundaries.md) defines per-item rejection and
  recovery after a batch write or projection failure.
- [Host adapters](host-adapters.md) defines lifecycle, executor, native-memory, and sandbox
  boundaries for supported agent hosts.
- [Event-driven automatic Dreaming](event-driven-auto-dreaming.md) defines due progress,
  detached execution, cross-host ownership, and recovery without a resident service.
- [Explicit raw evidence reads](raw-evidence-reads.md) defines the boundary between
  an explicit provenance read and the default retrieval policy.
- [Management operation boundaries](management-operation-boundaries.md) defines the
  correction, relationship mutation, automatic duplicate supersession, and automatic
  directory grouping contracts.
