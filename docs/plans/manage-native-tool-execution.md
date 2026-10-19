# Manage native-tool execution

## Preserved call chain

`mem sleep` and the one-shot Dream worker still enter `Manage.sleep()`. The method first performs
T0 maintenance deterministically: date normalization, weight settlement, co-occurrence links,
exact-duplicate invalidation, near-duplicate group repair, and clustering. It then computes T1
proposals, freezes their source hashes, and delegates only the review execution.

Text mode renders the original full prompt and parses JSON-line verdicts. Experimental native mode
sends compact proposal summaries to one isolated Codex run and serves a run-scoped
evidence/verdict toolkit over stdio MCP. Both return the same `ReviewOutcome`; Manage then enforces
per-kind caps and calls `decide()` only for a still-open proposal with unchanged sources.
`decide()` applies through Store methods and appends the Decision Ledger. Finally `Manage.sleep()`
writes the Dream Report and optionally commits the Store repository.

The manual path holds the Dream run and maintenance locks around `Manage.sleep()`. Automatic
Dreaming adds the persisted claim/lease and stable dream id, then the worker takes the same locks
and calls the same method. No resident backend is introduced.

## Reused transport and independent authority

PR #106's reusable piece is the executor transport: a Host can receive a per-job stdio MCP server.
The Write toolkit is not a Manage authority model. Manage does not expose Store record, correct,
delete, merge, generic memory, shell, or filesystem tools because those would bypass open-proposal
membership, caps, stale-target checks, the Decision Ledger, and report accounting.

`ManageReviewToolkit` exposes only:

- `list_proposals`: the authoritative menu for this run.
- `read_evidence`: bounded, pageable reads of targets named by one menu item.
- `submit_verdicts`: one complete judgement set under the existing verdict schema.

`Manage._review()` retains ownership of cap enforcement and calls the existing `decide()` path for
accepted verdicts. T0, proposal generation, claim/lease handling, locks, mutation guards, Decision
Ledger, Dream Report, and Git behavior remain unchanged. Text Host and endpoint paths remain the
default. The native tools validate run membership and source hashes, bound output and total
evidence, and persist a trace for the library to absorb after Codex exits.

## Runtime bounds and failure semantics

`manage.review_max_tool_calls`, per-result characters, and total evidence characters bound the MCP
surface; `[executor.manage].timeout_seconds` bounds the Host process. Codex's public CLI does not
offer a model-step flag, so `review_max_steps` is an audit ceiling used with the tool budget rather
than a claim that hidden model requests can be killed exactly. JSONL `turn.completed` supplies
token/cache totals and Host turn count when available.

A run with no accepted complete submission, a timeout, an invalid id, a stale source, or an
abnormal Host exit fails closed and never selects another reasoner. This limitation and the paired
quality/latency evidence keep native mode experimental.

## Authenticated Codex evidence

The opt-in system test completed the whole CLI path with local Codex 0.162.0 and
`gpt-5.6-sol` in 32.20 seconds: `mem sleep` generated a proposal, Codex called
`read_evidence`, then `submit_verdicts`, and Manage validated and wrote the Store, Decision
Ledger, and Dream Report. The test is skipped unless `AGENT_MEMORY_LIVE_CODEX=1` is set; the
normal suite never depends on credentials or a network service.

`tools/manage_review_benchmark.py` defines a fixed 12-case corpus across merge, supersede,
split, abstract-review, and delete proposals. On 2026-10-19 one authenticated, paired run used
four byte-identical Store pairs and alternated arm order. Text agreed with the fixed labels on
9/12 cases; Native agreed on 10/12. Both arms had zero runtime errors and complete Ledger and
Report output. Native read every target, using 26 successful tool calls (4 list, 18 read, 4
submit). It reported 177,866 input, 137,728 cached-input, and 2,524 output tokens. The Text
compatibility invocation did not expose token usage; its rendered prompts totalled 10,171
characters.

Native took 110.766 seconds versus Text's 59.496 seconds, 86.2% slower in this sample. Its one
additional labelled agreement was an explicitly obsolete delete proposal; both arms rejected a
labelled complementary merge and current-policy supersede. With 12 cases and one replay this is
an integration sample, not an accuracy benchmark under the repository's experiment rules. The
trace contained no repeated evidence reads, so the run did not justify a speculative performance
commit. Native remains opt-in while a larger repeated corpus and Host portability are open work.
