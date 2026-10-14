# Follow-ups

## Read policy follow-up

- Evaluate the memory-first reading policy with observed exposure before attributing
  answer changes to bounded Trace or optional Vector candidates.

## Management follow-ups

- Preserve identity and provenance when regrouping menu-based add-only schemas;
  the current move re-enters add-only naming and can replace the source file with
  a renamed record that does not inherit its evidence.
- Revalidate the duplicate keeper under the same writer lock as T0 invalidation; current
  stale-write detection protects only the record being invalidated.
- Decide explicit confirmation and host-level authorization for permanent GC, import and
  cross-store changes; CLI labels alone do not identify a human.
- Decide preimage retention and recovery guarantees for split and in-place correction,
  including stores outside Git and multi-file Manage failures.
- Decide whether direct link/unlink delta commands, relation audit history and per-operation
  bounds are needed; current correct replaces the complete list.
- Review recovery of interrupted multi-file operations outside Git-backed stores.

## Executor follow-ups

- Persist a per-run Write trace (messages, tool calls, operations, usage), add explicit cache
  breakpoints for endpoints that need them, a context provider per job, and a durable job queue
  in place of the fire-and-forget launch.
- Validate submissions against the Store, not only the reconcile sheet, so store-level refusals
  return inside the run instead of through the single-shot text repair.
- Move Hermes and Muse Code onto the MCP toolkit transport once their tools-only posture passes a
  live preflight; until then they keep the text protocol.
- Harness Claude Code runs with tools enabled still load the user's MCP servers; on a machine
  with many servers their tool definitions alone overflow Haiku's context, and any memory-like
  server contaminates attribution. Decide strict MCP for harness runs and record the change in
  the experiment ledger.
- A decision and a fact with the same key fields derive the same name: the second write is
  refused, and the text repair folded the decision into the fact (observed live with Codex,
  2026-10-14). Names, or the collision rule, need to account for type.
- Boundary distillation through the host CLI takes 80–100 s per boundary on Haiku (three
  negotiation rounds, one cold process each); measure again once the executor loop lands.
- Verify the Codex lifecycle hooks end to end, including the one-time hook trust review; the
  Codex Write executor is verified live, the hooks by unit tests only.

## Muse Code follow-ups

- Run the isolated Muse shell, lifecycle hook, and stdio MCP sandbox preflight on an installed,
  authenticated Muse build, then record the observed compatibility result.
- Run Muse-to-Muse, Muse-to-Codex, and Codex-to-Muse portability smoke before the full four-host
  matrix.
- Map `MUSE_SESSION_ID` into shared MCP source context only if provenance can accept it without a
  Muse-specific Store field.
- Validate the isolated root-session fixture against an exported log from the supported Muse
  version before treating raw-log fallback as release-ready.
