# Write negotiation

Write turns one archived batch into memory operations. The reasoner is a standard tool-using
agent: it decides what to look at, how often, and when it is done. The library supplies the tools,
validates what comes back, and owns every write.

## One toolkit

The Write toolkit is the only definition of what the reasoner may do during a batch:

- **recall** searches current memory and lists matches by handle;
- **read** opens one active memory in full;
- **submit operations** hands back the batch's operations under the operation schema.

A handle becomes nameable in update and supersede once the reconcile sheet or a tool result has
shown it; any other handle stays refused, so steering by conversation or recalled content can at
most produce a new file. A submission is checked against the reconcile sheet and then by the
Store's own write preparation, so the reasoner learns every refusal the write would raise inside
the same run; the latest accepted submission is the batch's answer. Tools never write the Store:
accepted operations reach it through the single write path, and only what a check cannot see —
siblings that collide with each other, or the Store changing underneath — falls to the repair
path.

The toolkit imposes no look budget, turn cap or forced final turn. Request and process timeouts
detect transport failure; they are not reasoning limits. Why: these are the industry-standard
mechanics of a tool-use agent, and they let the model use its full judgement instead of a
protocol written around its absence.

## Two transports

| Reasoner | Who runs the loop | How the tools arrive |
|---|---|---|
| Model endpoint | The executor | Native function calling over a structured message history |
| Claude Code, Codex | The host CLI, one headless run per batch | A per-batch stdio MCP adapter over the same toolkit |
| Muse Code (`tool_mode = "native"`) | The isolated host CLI, one headless run per batch | A required per-batch stdio MCP adapter selected as Muse's complete toolset |

The endpoint, Claude Code and Codex transports send the distillation instructions and type table
as the system prompt and the batch's reconcile sheet and conversation as the user message,
constant material first so prefixes stay cacheable. Muse preserves the same order in one prompt
file because its CLI has no system-prompt replacement flag. No transport carries tool semantics
(Invariant 8). On a host transport the toolkit state crosses the process boundary through the
batch's private scratch directory: seeded before the run, absorbed after it.

A run that ends without an accepted submission writes nothing and leaves the archive backlog and
Watermark untouched. Host and endpoint failures follow the attribution rules in
[Host adapters](host-adapters.md).

Hosts without a verified MCP posture keep the line-oriented text protocol: the library runs the
loop, parses looks and operations from plain text, and calls the same toolkit for recall and read.
`tool_mode = "auto"` preserves this protocol for Muse while keeping native tools as the default
for Claude Code and Codex. `native` and `text` select a Host path explicitly; an unsupported or
invalid selection fails rather than changing transport. Muse native mode requires 1.4.4 because
that release added exact MCP names to `run.toolset`. Its isolated settings contain only provider
routing and the required batch server; Shell, Web, file writes, reminders, personal context and
session persistence are disabled. Muse has no system-prompt replacement flag, so the same system
instructions and batch material are placed, in that order, in its one prompt file.
