"""The library-side distiller: the store's config names who reasons, the host CLI by default.

One extraction for every host (ADR-002 as amended). What is sent and what the reply may do
are decided in the core; this module only picks the pipe the text travels through. A host
whose dialect has an MCP posture runs as a tool-use agent over the Write toolkit; the rest
keep the text protocol.
"""

from __future__ import annotations

from agent_memory.core.config import REASONER_ENDPOINT, REASONER_HOST, ExecutorConfig
from agent_memory.core.errors import ReasonerUnavailableError

from .credentials import VertexCredentials
from .hosts import DIALECTS
from .reasoners import EndpointReasoner, HostReasoner, ToolHostReasoner


def distiller(config: ExecutorConfig) -> EndpointReasoner | HostReasoner:
    if config.reasoner == REASONER_HOST:
        dialect = DIALECTS.get(config.host)
        speaks_tools = dialect is not None and dialect.supports_tools
        chosen = ToolHostReasoner if speaks_tools else HostReasoner
        return chosen.for_host(config.host, model=config.host_model)
    if config.reasoner == REASONER_ENDPOINT:
        return EndpointReasoner(
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            credentials=VertexCredentials(project=config.project, location=config.location),
            base_url=config.endpoint,
        )
    raise ReasonerUnavailableError(f"unsupported reasoner {config.reasoner!r}")
