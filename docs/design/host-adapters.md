# Host adapters

Host support has two boundaries. Lifecycle adapters translate host events into injection,
eviction, and pause moments. Executor dialects translate a prompt and tool posture into one
headless host invocation and normalize only its final answer. Capture, archive, distillation,
Memory, Recall, and Manage stay host-neutral.

For Write negotiation, Claude Code and Codex run tools-only: the only tools are the Write
toolkit's, served by the per-batch MCP adapter ([Write negotiation](write-negotiation.md)); the
host's built-in tools, user configuration, rules and native memory are off and its system prompt
is replaced. Claude's bare mode stays unused because it drops OAuth and would break zero-key
install.

Muse native Write is opt-in because its verified compatibility floor differs from lifecycle
support. Muse 1.4.4 added exact MCP selection through `run.toolset`; native mode supplies that
selection as a one-run override and stages one required server in the already-isolated Muse
settings. Older CLIs fail with a version-specific error in the same attempted process. Automatic
mode continues to use the text protocol, so enabling Muse lifecycle support never silently
changes Write execution. Hermes has no native Write posture here.

Write and Manage have independent Store-level reasoner policies. Explicit CLI choices override
the operation policy, which overrides the legacy executor policy. Without an operation policy,
automatic Write uses the host that produced the source session while Manage uses the legacy
Store executor. The source host remains capture metadata and never overrides an explicit Write
reasoner.

Each operation may use a supported host CLI or a user-owned model endpoint. Authentication,
transport, host-process, and response-shape failures are attributed to that operation and stop
the attempt without selecting another host or endpoint. Write retains the unsettled archive
backlog, and every accepted memory continues to cite the original source session. Headless
reasoner sessions carry the executor marker so their lifecycle hooks remain inert.

Automatic Manage deliberately uses the Store's configured Manage reasoner, not the lifecycle
source Host. The selected reasoner kind, Host, and model are recorded in the claim and reported by
the worker; failure never falls back to another transport. On a fresh Host-backed Store, the first
successful Host setup also supplies the default Manage policy. Explicit operation policies and
legacy endpoint configuration are preserved.

`muse-code` is the canonical Muse Code identity and `muse` is only a setup alias and binary
name. Muse lifecycle events use the existing moments, and only root-session material enters the
archive. Muse's native memory remains independent and is never copied, synchronized, or treated
as Recall evidence.

Host setup is a preserving merge. Muse settings require their schema version, retain unknown
settings, hooks, and MCP servers, and are replaced atomically only after valid JSON is read.
The setup path installs lifecycle hooks and the canonical agent-memory skill; MCP remains an
explicit use of the shared server.

Muse 1.4 lifecycle payloads identify the session but set `transcript_path` to null. The Muse
adapter resolves that identifier to the root durable log under Muse's XDG data directory and
normalizes only user and assistant conversation records. Child and observer logs remain excluded.

Muse reasoning runs through the host CLI. Prompts use temporary files, model and reasoning
overrides are opt-in, and Muse JSONL is normalized inside its executor dialect. Experiment
metadata fixes host identity, CLI version, model, reasoning effort, workspace, and revision.

Muse's sandbox remains enabled. Experiment Stores and workdirs must share a bounded workspace;
ordinary external Stores are read-only to the agent shell. Controlled runs isolate HOME and XDG
state while reusing only an explicit auth file. Hook and MCP writes require a live compatibility
preflight. Results are not attributable until native memory is isolated and the tested build
passes that preflight.
