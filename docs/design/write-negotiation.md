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
most produce a new file. A refused submission returns per-operation reasons to the reasoner in
the same run, and the latest accepted submission is the batch's answer. Tools never write the
Store: accepted operations reach it through the single write path, and store-level rejections
take the existing repair path.

The toolkit imposes no look budget, turn cap or forced final turn. Request and process timeouts
detect transport failure; they are not reasoning limits. Why: these are the industry-standard
mechanics of a tool-use agent, and they let the model use its full judgement instead of a
protocol written around its absence.

## Two transports

| Reasoner | Who runs the loop | How the tools arrive |
|---|---|---|
| Model endpoint | The executor | Native function calling over a structured message history |
| Claude Code, Codex | The host CLI, one headless run per batch | A per-batch stdio MCP adapter over the same toolkit |

Both transports send the distillation instructions and type table as the system prompt and the
batch's reconcile sheet and conversation as the user message, constant material first so prefixes
stay cacheable. Neither carries tool semantics (Invariant 8). On the host transport the toolkit
state crosses the process boundary through the batch's private scratch directory: seeded before
the run, absorbed after it.

A run that ends without an accepted submission writes nothing and leaves the archive backlog and
Watermark untouched. Host and endpoint failures follow the attribution rules in
[Host adapters](host-adapters.md).

Hosts without a verified MCP posture keep the line-oriented text protocol: the library runs the
loop, parses looks and operations from plain text, and calls the same toolkit for recall and read.
