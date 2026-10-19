"""Manage review tools expose evidence and verdicts, never Store mutation."""

import json

from agent_memory.core import reasoning
from agent_memory.core.manage import Manage
from agent_memory.core.manage_toolkit import (
    ARG_NAME,
    ARG_OFFSET,
    ARG_PROPOSAL,
    ARG_VERDICTS,
    TOOL_LIST,
    TOOL_READ,
    TOOL_SUBMIT,
    ManageReviewToolkit,
)


def _kit(store, *, max_calls=24, result_chars=8000, evidence_chars=32000):
    store.record(
        type="experience",
        name="drain-window-first",
        abstract="Queue drain timeout expires before the worker lease completes",
        body="The drain is 20 seconds and the worker lease is 30 seconds.",
    )
    store.record(
        type="experience",
        name="drain-window-second",
        abstract="Queue drain timeout expires before the worker lease completes on staging",
        body="The staging drain is 20 seconds and the worker lease is 30 seconds.",
    )
    proposals = Manage(store).proposals()
    request = reasoning.prepare(
        proposals,
        store.records(),
        reasoning.ReviewLimits(8, max_calls, 120.0, result_chars, evidence_chars),
    )
    return ManageReviewToolkit(store, request), proposals[0]


def _reject(proposal_id):
    return {"proposal": proposal_id, "verdict": "reject"}


def test_catalogue_contains_only_scoped_review_capabilities(store):
    kit, _ = _kit(store)
    assert {spec.name for spec in kit.catalogue()} == {TOOL_LIST, TOOL_READ, TOOL_SUBMIT}
    assert all(word not in spec.name for spec in kit.catalogue() for word in ("delete", "correct"))


def test_list_is_compact_and_read_opens_only_named_evidence(store):
    kit, proposal = _kit(store)
    listed = kit.call(TOOL_LIST, {})
    assert not listed.is_error
    assert proposal.id in listed.text
    assert "The staging drain is 20 seconds" not in listed.text

    refused = kit.call(
        TOOL_READ,
        {ARG_PROPOSAL: proposal.id, ARG_NAME: "not-a-target"},
    )
    assert refused.is_error
    read = kit.call(
        TOOL_READ,
        {ARG_PROPOSAL: proposal.id, ARG_NAME: proposal.targets[1]},
    )
    assert not read.is_error
    payload = json.loads(read.text)
    assert payload["source_hash"]
    assert "staging drain is 20 seconds" in payload["body"]
    assert kit.evidence_reads == [(proposal.id, proposal.targets[1])]


def test_read_pages_large_evidence_with_per_call_and_run_budgets(store):
    kit, proposal = _kit(store, result_chars=600, evidence_chars=40)
    first = kit.call(
        TOOL_READ,
        {ARG_PROPOSAL: proposal.id, ARG_NAME: proposal.targets[0]},
    )
    assert not first.is_error
    payload = json.loads(first.text)
    assert len(payload["body"]) <= 40
    exhausted = kit.call(
        TOOL_READ,
        {
            ARG_PROPOSAL: proposal.id,
            ARG_NAME: proposal.targets[0],
            ARG_OFFSET: payload["next_offset"],
        },
    )
    assert exhausted.is_error
    assert "budget exhausted" in exhausted.text


def test_submit_accepts_one_complete_set_but_never_mutates_or_decides(store):
    kit, proposal = _kit(store)
    before = {record.name: record.to_text() for record in store.records()}
    reply = kit.call(TOOL_SUBMIT, {ARG_VERDICTS: [_reject(proposal.id)]})
    assert not reply.is_error
    assert kit.outcome().complete
    assert kit.submission and kit.submission[0].proposal_id == proposal.id
    assert {record.name: record.to_text() for record in store.records()} == before
    assert Manage(store).proposals()[0].id == proposal.id

    repeated = kit.call(TOOL_SUBMIT, {ARG_VERDICTS: [_reject(proposal.id)]})
    assert repeated.is_error
    assert "already accepted" in repeated.text


def test_submit_refuses_foreign_missing_and_duplicate_proposal_ids(store):
    kit, proposal = _kit(store)
    foreign = kit.call(TOOL_SUBMIT, {ARG_VERDICTS: [_reject("foreign-proposal")]})
    assert foreign.is_error
    assert "outside this run" in foreign.text and "missing proposal ids" in foreign.text

    duplicate = kit.call(
        TOOL_SUBMIT,
        {ARG_VERDICTS: [_reject(proposal.id), _reject(proposal.id)]},
    )
    assert duplicate.is_error
    assert "duplicate proposal ids" in duplicate.text
    assert kit.submission is None


def test_submit_refuses_a_source_that_changed_after_proposal_generation(store):
    kit, proposal = _kit(store)
    store.correct(proposal.targets[0], body="Concurrent writer changed this evidence.")
    reply = kit.call(TOOL_SUBMIT, {ARG_VERDICTS: [_reject(proposal.id)]})
    assert reply.is_error
    assert "changed after proposal generation" in reply.text
    assert kit.submission is None


def test_tool_call_budget_fails_closed_without_a_submission(store):
    kit, proposal = _kit(store, max_calls=1)
    assert not kit.call(TOOL_LIST, {}).is_error
    refused = kit.call(TOOL_SUBMIT, {ARG_VERDICTS: [_reject(proposal.id)]})
    assert refused.is_error
    assert not kit.outcome().complete
    assert kit.submission is None


def test_session_seed_and_record_round_trip(store, tmp_path):
    kit, proposal = _kit(store)
    directory = tmp_path / "review"
    directory.mkdir()
    kit.save_seed(directory)
    child = ManageReviewToolkit.from_directory(directory)
    child.call(
        TOOL_READ,
        {ARG_PROPOSAL: proposal.id, ARG_NAME: proposal.targets[0]},
    )
    child.call(TOOL_SUBMIT, {ARG_VERDICTS: [_reject(proposal.id)]})
    child.save_record(directory)

    kit.absorb_directory(directory)
    assert kit.outcome().complete
    assert kit.evidence_reads == [(proposal.id, proposal.targets[0])]
    assert [call.name for call in kit.calls] == [TOOL_READ, TOOL_SUBMIT]
