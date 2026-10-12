# Event-driven automatic Dreaming

Automatic Dreaming extends the file-first lifecycle rather than adding a Memory service.
Lifecycle activity supplies opportunities to inspect durable progress. A completed boundary
distillation may claim due work and start one detached, short-lived worker; an otherwise empty
boundary or a later SessionStart is also a recovery and elapsed-time opportunity.

A session counts once when captured material exists, its distillation watermark has caught up,
and no pending or redistill work remains. Hook frequency is not progress. The first Dream uses
the configured session threshold. Later Dreams require both the configured elapsed-time and new
session thresholds. Manage waits while any captured Write remains unsettled.

Claims are Store-local persistent state. A claim binds a stable decision identity, the covered
session set, the triggering Host, an attempt, and a lease. Store-local advisory locks serialize
claiming and execution; Distillation and Manage share a maintenance gate. A completed report is
the success fence, so recovery after a state-write crash does not repeat Manage. A missing report
after a failed process remains retryable when the lease expires and another lifecycle event
arrives.

The lifecycle Host that first claims due work supplies the headless reasoner. This keeps Codex,
Claude Code, and Muse on their existing login and avoids endpoint fallback. On a fresh
Host-backed Store, the first successful Host setup supplies the default manual Manage policy;
explicit operation policies and legacy endpoint configuration are preserved.

There is no timer, listener, supervisor, or resident process. With no Host activity, elapsed-time
eligibility remains dormant. The next lifecycle event checks it. Operators that require wall-clock
scheduling must provide an external scheduler; that is an optional integration, not an installed
Memory runtime.
