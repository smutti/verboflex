"""Destination partitioning is tested with the real Phase6 renderer and proof."""

import asyncio
import sys
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tests.unit.services.test_writeback import scenario  # noqa: E402
from verboflex.localization.writing.core import WritebackReason, WritebackRejected
from verboflex.schemas.submissions import MappingTarget
from verboflex.services import submission_selection as service
from verboflex.services.submission_selection import partition_selection, prepare_submission_groups


def two_destinations(monkeypatch):
    data = scenario(monkeypatch, four=False)
    mapping = data.captured.mappings[0]
    original = data.captured.proposals[0]
    second_file = replace(
        data.captured.files[0],
        mapping_id=uuid4(),
        authority=replace(data.captured.files[0].authority, import_execution_id=uuid4()),
    )
    second_edit = replace(second_file.edits[0], replacement_text="other")
    second_file = replace(second_file, edits=(second_edit,))
    second_mapping = replace(
        mapping,
        mapping_id=second_file.mapping_id,
        scope_id=uuid4(),
        execution_id=second_file.authority.import_execution_id,
        source_references=(second_file.authority,),
        allowed_targets=(("release", True),),
    )
    second_proposal = replace(
        original,
        proposal_id=uuid4(),
        key_id=uuid4(),
        members=(
            replace(
                original.members[0],
                value_id=uuid4(),
                authority=second_file.authority,
                edit=second_edit,
            ),
        ),
    )
    data.captured = replace(
        data.captured,
        proposals=(original, second_proposal),
        mappings=(mapping, second_mapping),
        files=(data.captured.files[0], second_file),
    )

    def capture(_session, *, selection, **_):
        ids = {p.proposal_id for p in selection.proposals}
        proposals = tuple(p for p in data.captured.proposals if p.proposal_id in ids)
        execution_ids = {m.authority.import_execution_id for p in proposals for m in p.members}
        mappings = tuple(m for m in data.captured.mappings if m.execution_id in execution_ids)
        mapping_ids = {m.mapping_id for m in mappings}
        return replace(
            data.captured,
            proposals=proposals,
            mappings=mappings,
            files=tuple(f for f in data.captured.files if f.mapping_id in mapping_ids),
        )

    monkeypatch.setattr(data.service, "capture_writeback_authority", capture)
    return data


def prepare(data, targets=()):
    return asyncio.run(
        prepare_submission_groups(
            data.factory, authority=data.captured, targets=targets, adapter=data.adapter
        )
    )


def test_different_targets_same_path_keep_edits_isolated(monkeypatch):
    data = two_destinations(monkeypatch)
    reviewed = prepare(data)
    assert len(reviewed.groups) == 2
    by_target = {g.target_branch: g for g in reviewed.groups}
    assert b">new<" in by_target["main"].prepared.files[0].content
    assert b">other<" not in by_target["main"].prepared.files[0].content
    assert b">other<" in by_target["release"].prepared.files[0].content
    assert b">new<" not in by_target["release"].prepared.files[0].content
    assert all(len(g.prepared.selection.proposals) == 1 for g in reviewed.groups)
    again = prepare(data)
    assert again.content_digest == reviewed.content_digest
    assert {g.id for g in again.groups}.isdisjoint(g.id for g in reviewed.groups)


def test_review_captures_provider_uuid_independent_of_local_repository_id(monkeypatch):
    from uuid import NAMESPACE_URL, uuid5

    data = two_destinations(monkeypatch)
    review = prepare(data)
    for group in review.groups:
        expected = uuid5(NAMESPACE_URL, f"{group.workspace}/{group.repository_slug}")
        assert group.repository_id != expected
        assert getattr(group, "provider_repository_id", None) == expected


def test_repository_replacement_during_review_cannot_be_ready(monkeypatch):
    data = two_destinations(monkeypatch)
    original = data.adapter.read_repository_metadata
    calls = 0

    async def replaced(session, **kwargs):
        nonlocal calls
        result = await original(session, **kwargs)
        calls += 1
        if calls > 1:
            result["uuid"] = str(uuid4())
        return result

    data.adapter.read_repository_metadata = replaced
    with pytest.raises(WritebackRejected):
        prepare(data)


def test_group_partition_keeps_batch_byte_limit(monkeypatch):
    data = two_destinations(monkeypatch)
    original_size = data.captured.files[0].authority.size_bytes
    monkeypatch.setattr(service, "MAX_CANONICAL_AGGREGATE_BYTES", original_size + 1)
    with pytest.raises(WritebackRejected) as error:
        prepare(data)
    assert error.value.reason == WritebackReason.LIMIT_EXCEEDED


def test_per_mapping_target_authority_is_not_a_union(monkeypatch):
    data = two_destinations(monkeypatch)
    with pytest.raises(WritebackRejected):
        partition_selection(
            data.captured,
            targets=(
                MappingTarget(
                    mapping_id=data.captured.mappings[0].mapping_id, target_branch="release"
                ),
            ),
        )
    assert data.adapter.calls == []


def test_same_target_conflicting_file_edits_refused(monkeypatch):
    data = two_destinations(monkeypatch)
    data.captured = replace(
        data.captured,
        mappings=tuple(
            replace(m, allowed_targets=(("main", True),)) for m in data.captured.mappings
        ),
    )
    assert len(partition_selection(data.captured)) == 1
    with pytest.raises(WritebackRejected):
        prepare(data)


@pytest.mark.parametrize("count,accepted", [(0, False), (1, True), (100, True), (101, False)])
def test_exact_proposal_limit_has_no_truncation(monkeypatch, count, accepted):
    data = scenario(monkeypatch, four=False)
    first = data.captured.proposals[0]
    authority = replace(
        data.captured, proposals=tuple(replace(first, proposal_id=uuid4()) for _ in range(count))
    )
    if accepted:
        groups = partition_selection(authority)
        assert sum(len(g.selection.proposals) for g in groups) == count
    else:
        with pytest.raises(WritebackRejected):
            partition_selection(authority)


def test_duplicate_and_foreign_target_rejected(monkeypatch):
    data = scenario(monkeypatch, four=False)
    with pytest.raises(WritebackRejected):
        partition_selection(replace(data.captured, proposals=data.captured.proposals * 2))
    with pytest.raises(WritebackRejected):
        partition_selection(
            data.captured, targets=(MappingTarget(mapping_id=uuid4(), target_branch="main"),)
        )


@pytest.mark.parametrize("count", [20, 21])
def test_exact_group_limit(monkeypatch, count):
    data = scenario(monkeypatch, four=False)
    mapping, proposal = data.captured.mappings[0], data.captured.proposals[0]
    mappings, proposals = [], []
    for _ in range(count):
        mid, rid, execution = uuid4(), uuid4(), uuid4()
        authority = replace(
            proposal.members[0].authority, repository_id=rid, import_execution_id=execution
        )
        mappings.append(
            replace(
                mapping,
                mapping_id=mid,
                execution_id=execution,
                sides=(replace(mapping.sides[0], repository_id=rid),),
                source_references=(authority,),
            )
        )
        proposals.append(
            replace(
                proposal,
                proposal_id=uuid4(),
                members=(replace(proposal.members[0], authority=authority),),
            )
        )
    captured = replace(data.captured, proposals=tuple(proposals), mappings=tuple(mappings))
    if count == 20:
        assert len(partition_selection(captured)) == count
    else:
        with pytest.raises(WritebackRejected):
            partition_selection(captured)


def test_group_partition_keeps_cumulative_output_expansion_limit(monkeypatch):
    data = two_destinations(monkeypatch)
    changed_proposals, changed_files = [], []
    for proposal, file in zip(data.captured.proposals, data.captured.files, strict=True):
        edit = replace(file.edits[0], replacement_text="n" * 80)
        changed_files.append(replace(file, edits=(edit,)))
        changed_proposals.append(
            replace(proposal, members=(replace(proposal.members[0], edit=edit),))
        )
    data.captured = replace(
        data.captured, proposals=tuple(changed_proposals), files=tuple(changed_files)
    )
    assert sum(f.authority.size_bytes for f in data.captured.files) < 200
    assert (
        sum(
            len(m.edit.expected_text) + len(m.edit.replacement_text)
            for p in data.captured.proposals
            for m in p.members
        )
        < 200
    )
    monkeypatch.setattr(service, "MAX_CANONICAL_AGGREGATE_BYTES", 200)
    with pytest.raises(WritebackRejected) as error:
        prepare(data)
    assert error.value.reason == WritebackReason.LIMIT_EXCEEDED
