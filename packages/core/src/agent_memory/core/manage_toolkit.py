"""Run-scoped tools for reviewing Manage proposals without mutation authority."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import pathlib
import tempfile

from . import reasoning
from .store import Store
from .toolkit import ToolCall, ToolReply, ToolSpec

TOOL_LIST = "list_proposals"
TOOL_READ = "read_evidence"
TOOL_SUBMIT = "submit_verdicts"
TOOLS = (TOOL_LIST, TOOL_READ, TOOL_SUBMIT)
ARG_PROPOSAL = "proposal"
ARG_NAME = "name"
ARG_OFFSET = "offset"
ARG_VERDICTS = "verdicts"
SEED_FILENAME = "seed.json"
RECORD_FILENAME = "record.json"
OUTPUT_RESERVE_CHARS = 512
MIN_SPLIT_PARTS = 2
EVIDENCE_READ_FIELDS = 2

VERDICT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        reasoning.FIELD_PROPOSAL: {"type": "string"},
        reasoning.FIELD_VERDICT: {
            "type": "string",
            "enum": [reasoning.VERDICT_ACCEPT, reasoning.VERDICT_REJECT],
        },
        reasoning.FIELD_TEXT: {"type": "string"},
        reasoning.FIELD_ABSTRACT: {"type": "string"},
        reasoning.FIELD_BODY: {"type": "string"},
        reasoning.FIELD_PARTS: {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    reasoning.FIELD_ABSTRACT: {"type": "string"},
                    reasoning.FIELD_BODY: {"type": "string"},
                    reasoning.FIELD_PROVENANCE: {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [reasoning.FIELD_ABSTRACT, reasoning.FIELD_BODY],
            },
        },
    },
    "required": [reasoning.FIELD_PROPOSAL, reasoning.FIELD_VERDICT],
}

CATALOGUE = (
    ToolSpec(
        TOOL_LIST,
        "List every proposal in this Manage review run and its allowed evidence handles. "
        "This tool reads no Store content and cannot change memory.",
        {"type": "object", "properties": {}},
    ),
    ToolSpec(
        TOOL_READ,
        "Read a bounded page of evidence for one proposal target. Only targets listed for this "
        "run are readable. Use offset from the prior result to continue a long body.",
        {
            "type": "object",
            "properties": {
                ARG_PROPOSAL: {"type": "string"},
                ARG_NAME: {"type": "string"},
                ARG_OFFSET: {"type": "integer", "minimum": 0},
            },
            "required": [ARG_PROPOSAL, ARG_NAME],
        },
    ),
    ToolSpec(
        TOOL_SUBMIT,
        "Submit exactly one verdict for every proposal in this run. Invalid, duplicate, foreign, "
        "or stale proposals are refused. This tool never applies a verdict or writes the Store.",
        {
            "type": "object",
            "properties": {
                ARG_VERDICTS: {
                    "type": "array",
                    "items": VERDICT_SCHEMA,
                    "minItems": 1,
                }
            },
            "required": [ARG_VERDICTS],
        },
    ),
)


class ManageReviewToolkit:
    """The complete capability surface available to one native Manage reviewer."""

    def __init__(self, store: Store, request: reasoning.ReviewRequest):
        self.store = store
        self.request = request
        self.submission: tuple[reasoning.Verdict, ...] | None = None
        self.calls: list[ToolCall] = []
        self.evidence_chars = 0
        self.evidence_reads: list[tuple[str, str]] = []

    def catalogue(self) -> tuple[ToolSpec, ...]:
        return CATALOGUE

    def call(self, name: str, arguments: object) -> ToolReply:
        given = arguments if isinstance(arguments, dict) else {}
        budget = min(self.request.limits.max_tool_calls, self.request.limits.max_steps)
        if len(self.calls) >= budget:
            reply = ToolReply("review tool-call budget exhausted", True)
        elif name == TOOL_LIST:
            reply = self._list(given)
        elif name == TOOL_READ:
            reply = self._read(given)
        elif name == TOOL_SUBMIT:
            reply = self._submit(given)
        else:
            reply = ToolReply(f"unknown tool; the tools are {', '.join(TOOLS)}", True)
        reply = ToolReply(self._clip(reply.text), reply.is_error)
        self.calls.append(ToolCall(name, given, reply))
        return reply

    def outcome(self) -> reasoning.ReviewOutcome:
        submitted = self.submission is not None
        return reasoning.ReviewOutcome(
            verdicts=self.submission or (),
            submitted=submitted,
            complete=submitted,
            mode="native",
            rounds=min(len(self.calls) + 1, self.request.limits.max_steps),
            tool_calls=len(self.calls),
            evidence_reads=tuple(self.evidence_reads),
            tool_trace=tuple((call.name, call.reply.is_error) for call in self.calls),
            error="" if submitted else "native reviewer submitted no complete verdict set",
        )

    def _list(self, arguments: dict[str, object]) -> ToolReply:
        if arguments:
            return ToolReply("list_proposals takes no arguments", True)
        payload = [proposal.as_dict() for proposal in self.request.proposals]
        return ToolReply(json.dumps(payload, sort_keys=True))

    def _read(self, arguments: dict[str, object]) -> ToolReply:
        proposal_id = arguments.get(ARG_PROPOSAL)
        name = arguments.get(ARG_NAME)
        offset = arguments.get(ARG_OFFSET, 0)
        if not isinstance(proposal_id, str) or not isinstance(name, str):
            return ToolReply("read_evidence needs proposal and name", True)
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            return ToolReply("read_evidence offset must be a non-negative integer", True)
        proposal = self._proposal(proposal_id)
        if proposal is None:
            return ToolReply(f"proposal {proposal_id!r} is not in this review run", True)
        source = next((item for item in proposal.sources if item.name == name), None)
        if source is None:
            return ToolReply(f"memory {name!r} is not evidence for proposal {proposal_id}", True)
        stale = self._stale(source)
        if stale:
            return ToolReply(stale, True)
        remaining = self.request.limits.evidence_chars - self.evidence_chars
        if remaining <= 0:
            return ToolReply("review evidence budget exhausted", True)
        page_limit = max(1, self.request.limits.tool_result_chars - OUTPUT_RESERVE_CHARS)
        body = source.body
        chunk = body[offset : offset + min(page_limit, remaining)]
        self.evidence_chars += len(chunk)
        self.evidence_reads.append((proposal_id, name))
        next_offset = offset + len(chunk)
        payload = {
            "proposal": proposal_id,
            "name": source.name,
            "source_hash": source.source_hash,
            "type": source.type,
            "abstract": source.abstract,
            "provenance": list(source.provenance),
            "body": chunk,
            "offset": offset,
            "next_offset": next_offset if next_offset < len(body) else None,
        }
        return ToolReply(json.dumps(payload, sort_keys=True))

    def _submit(self, arguments: dict[str, object]) -> ToolReply:
        if self.submission is not None:
            return ToolReply("a complete verdict set was already accepted", True)
        raw = arguments.get(ARG_VERDICTS)
        if not isinstance(raw, list) or not raw:
            return ToolReply("submit_verdicts needs a non-empty verdicts list", True)
        verdicts: list[reasoning.Verdict] = []
        problems: list[str] = []
        for index, payload in enumerate(raw):
            verdict = reasoning.verdict_from_payload(payload)
            if verdict is None:
                problems.append(f"verdict {index}: invalid verdict object")
            else:
                verdicts.append(verdict)
        allowed = {proposal.id: proposal for proposal in self.request.proposals}
        given_ids = [verdict.proposal_id for verdict in verdicts]
        duplicates = sorted({item for item in given_ids if given_ids.count(item) > 1})
        foreign = sorted(set(given_ids) - set(allowed))
        missing = sorted(set(allowed) - set(given_ids))
        if duplicates:
            problems.append("duplicate proposal ids: " + ", ".join(duplicates))
        if foreign:
            problems.append("proposal ids outside this run: " + ", ".join(foreign))
        if missing:
            problems.append("missing proposal ids: " + ", ".join(missing))
        for verdict in verdicts:
            proposal = allowed.get(verdict.proposal_id)
            if proposal is None:
                continue
            problems.extend(self._verdict_problems(proposal, verdict))
            problems.extend(filter(None, (self._stale(source) for source in proposal.sources)))
        if problems:
            return ToolReply("Nothing was accepted.\n" + "\n".join(problems), True)
        self.submission = tuple(verdicts)
        return ToolReply(f"accepted {len(verdicts)} verdicts for Manage validation")

    @staticmethod
    def _verdict_problems(
        proposal: reasoning.ReviewProposal, verdict: reasoning.Verdict
    ) -> list[str]:
        if not verdict.accept:
            return []
        if proposal.kind == reasoning.PROPOSAL_MERGE and (
            not verdict.abstract.strip() or not verdict.body.strip()
        ):
            return [f"proposal {proposal.id}: accepted merge needs abstract and body"]
        if proposal.kind == reasoning.PROPOSAL_SPLIT:
            complete = [
                part for part in verdict.parts if part.abstract.strip() and part.body.strip()
            ]
            if len(complete) < MIN_SPLIT_PARTS:
                return [f"proposal {proposal.id}: accepted split needs at least two complete parts"]
        if proposal.kind == reasoning.PROPOSAL_ABSTRACT_REVIEW and not verdict.text.strip():
            return [f"proposal {proposal.id}: accepted abstract review needs text"]
        return []

    def _proposal(self, proposal_id: str) -> reasoning.ReviewProposal | None:
        return next((item for item in self.request.proposals if item.id == proposal_id), None)

    def _stale(self, source: reasoning.ReviewSource) -> str:
        current = self.store.find(source.name)
        if current is None or not current.is_active():
            return f"evidence {source.name!r} is no longer active"
        current_hash = (
            current.source_hash or hashlib.sha256(current.to_text().encode("utf-8")).hexdigest()
        )
        if current_hash != source.source_hash:
            return f"evidence {source.name!r} changed after proposal generation"
        return ""

    def _clip(self, text: str) -> str:
        limit = self.request.limits.tool_result_chars
        return text if len(text) <= limit else text[:limit] + "\n(truncated)"

    def seed(self) -> dict[str, object]:
        return {"store": str(self.store.root), "request": dataclasses.asdict(self.request)}

    def record(self) -> dict[str, object]:
        return {
            "submission": (
                [reasoning.verdict_as_dict(verdict) for verdict in self.submission]
                if self.submission is not None
                else None
            ),
            "evidence_chars": self.evidence_chars,
            "evidence_reads": [list(item) for item in self.evidence_reads],
            "calls": [
                {
                    "name": call.name,
                    "arguments": call.arguments,
                    "text": call.reply.text,
                    "is_error": call.reply.is_error,
                }
                for call in self.calls
            ],
        }

    def absorb(self, record: dict[str, object]) -> None:
        submission = record.get("submission")
        if isinstance(submission, list):
            verdicts = [reasoning.verdict_from_payload(item) for item in submission]
            if all(verdict is not None for verdict in verdicts):
                self.submission = tuple(verdict for verdict in verdicts if verdict is not None)
        self.evidence_chars = _int(record.get("evidence_chars"))
        self.evidence_reads = [
            (str(item[0]), str(item[1]))
            for item in _list(record.get("evidence_reads"))
            if isinstance(item, list) and len(item) == EVIDENCE_READ_FIELDS
        ]
        self.calls.extend(
            ToolCall(
                str(call.get("name") or ""),
                _dict(call.get("arguments")),
                ToolReply(str(call.get("text") or ""), bool(call.get("is_error"))),
            )
            for call in _dicts(record.get("calls"))
        )

    def save_seed(self, directory: pathlib.Path) -> None:
        _write_json(directory / SEED_FILENAME, self.seed())

    def save_record(self, directory: pathlib.Path) -> None:
        _write_json(directory / RECORD_FILENAME, self.record())

    def absorb_directory(self, directory: pathlib.Path) -> None:
        path = directory / RECORD_FILENAME
        if path.exists():
            self.absorb(json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def from_directory(cls, directory: pathlib.Path) -> ManageReviewToolkit:
        seed = json.loads((directory / SEED_FILENAME).read_text(encoding="utf-8"))
        return cls(
            Store(str(seed["store"]), agent="manage-review-toolkit"),
            _request(_dict(seed.get("request"))),
        )


def _request(raw: dict[str, object]) -> reasoning.ReviewRequest:
    proposals = []
    all_sources = tuple(_source(item) for item in _dicts(raw.get("sources")))
    by_name = {source.name: source for source in all_sources}
    for item in _dicts(raw.get("proposals")):
        source_names = [str(source.get("name") or "") for source in _dicts(item.get("sources"))]
        proposals.append(
            reasoning.ReviewProposal(
                id=str(item.get("id") or ""),
                kind=str(item.get("kind") or ""),
                targets=tuple(str(value) for value in _list(item.get("targets"))),
                reason=str(item.get("reason") or ""),
                evidence=str(item.get("evidence") or ""),
                sources=tuple(by_name[name] for name in source_names if name in by_name),
            )
        )
    limits = _dict(raw.get("limits"))
    return reasoning.ReviewRequest(
        proposals=tuple(proposals),
        sources=all_sources,
        limits=reasoning.ReviewLimits(
            max_steps=int(limits.get("max_steps") or 0),
            max_tool_calls=int(limits.get("max_tool_calls") or 0),
            timeout_seconds=float(limits.get("timeout_seconds") or 0),
            tool_result_chars=int(limits.get("tool_result_chars") or 0),
            evidence_chars=int(limits.get("evidence_chars") or 0),
        ),
    )


def _source(raw: dict[str, object]) -> reasoning.ReviewSource:
    return reasoning.ReviewSource(
        name=str(raw.get("name") or ""),
        source_hash=str(raw.get("source_hash") or ""),
        type=str(raw.get("type") or ""),
        abstract=str(raw.get("abstract") or ""),
        body=str(raw.get("body") or ""),
        provenance=tuple(str(value) for value in _list(raw.get("provenance"))),
    )


def _list(value: object) -> list:
    return value if isinstance(value, list) else []


def _dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _dicts(value: object) -> list[dict]:
    return [item for item in _list(value) if isinstance(item, dict)]


def _int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _write_json(path: pathlib.Path, payload: dict[str, object]) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    os.replace(temporary, path)
