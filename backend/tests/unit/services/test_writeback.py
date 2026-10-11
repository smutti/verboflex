"""Credential-free preparation uses bounded reads and immutable complete authority."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, replace
from types import SimpleNamespace
from uuid import uuid4

import pytest

from verboflex.integrations.bitbucket.client import (
    BitbucketBranch,
    BitbucketProviderReadError,
    BitbucketSourceMetadata,
)
from verboflex.localization.importing.core import CanonicalParserInput
from verboflex.localization.importing.registry import parse_canonical_snapshot
from verboflex.localization.writing.core import (
    SourceFileAuthority,
    WritebackReason,
    WritebackRejected,
    WriteEdit,
)
from verboflex.services.writeback_authority import (
    CapturedFile,
    CapturedMapping,
    CapturedMember,
    CapturedProposal,
    CapturedSourceSide,
    CapturedWritebackAuthority,
    ProposalSelection,
    WritebackSelection,
)


class Factory:
    def __init__(self):
        self.capture_open = False
        self.sessions = []

    @contextmanager
    def begin(self):
        self.capture_open = True
        try:
            yield object()
        finally:
            self.capture_open = False

    @contextmanager
    def __call__(self):
        session = object()
        self.sessions.append(session)
        yield session


class ReadOnlyAdapter:
    def __init__(self, scenario):
        self.scenario = scenario
        self.calls = []
        self.heads = {}
        self.after_read = lambda: None
        self.error = None

    def _record(self, operation, session, kwargs):
        assert not self.scenario.factory.capture_open, "database capture held across provider I/O"
        self.calls.append((operation, session, kwargs))
        if self.error is not None:
            raise self.error

    async def resolve_repository_branch(self, session, **kwargs):
        self._record("head", session, kwargs)
        return BitbucketBranch(
            kwargs["branch"], self.heads.get(kwargs["repository_slug"], "a" * 40)
        )

    async def read_repository_metadata(self, session, **kwargs):
        from uuid import NAMESPACE_URL, uuid5

        self._record("repository", session, kwargs)
        name = f"{kwargs['workspace']}/{kwargs['repository_slug']}"
        return {"type": "repository", "full_name": name, "uuid": str(uuid5(NAMESPACE_URL, name))}

    async def read_repository_source_metadata(self, session, **kwargs):
        self._record("meta", session, kwargs)
        content = self.scenario.contents[kwargs["repository_slug"], kwargs["path"]]
        return BitbucketSourceMetadata(kwargs["path"], kwargs["commit_hash"], len(content), ())

    async def read_repository_source_file(self, session, **kwargs):
        self._record("raw", session, kwargs)
        content = self.scenario.contents[kwargs["repository_slug"], kwargs["path"]]
        assert len(content) <= kwargs["max_bytes"]
        self.after_read()
        return content


def scenario(monkeypatch, *, four=True):
    service = importlib.import_module("verboflex.services.writeback")
    cases = [
        (
            "android_xml",
            "app/res/values-it/strings.xml",
            "app/res",
            b'<resources><string name="k">old</string></resources>',
        ),
        ("json", "it.json", "json:flat-per-locale:{locale}.json", b'{"k":"old"}'),
        (
            "ios_strings",
            "it.lproj/Localizable.strings",
            "ios-strings:{locale}.lproj/Localizable.strings",
            b'"k"="old";',
        ),
        (
            "qt_ts",
            "app_it.ts",
            "qt-ts:app_{locale}.ts",
            b'<TS version="2.1" language="it"><context><name>Main</name>'
            b'<message id="k"><source>Source</source><translation>old</translation>'
            b"</message></context></TS>",
        ),
    ]
    actor_id = uuid4()
    files, mappings, proposals, contents = [], [], [], {}
    for format_name, path, layout, content in cases if four else cases[:1]:
        repository_id, mapping_id, execution_id = uuid4(), uuid4(), uuid4()
        parser = CanonicalParserInput(format_name, "direct", path, content, layout, 1, "en")
        parsed = parse_canonical_snapshot(parser)
        assert not parsed.issues
        value = parsed.values[0]
        edit = WriteEdit(
            value.logical_key,
            value.language,
            value.selector,
            value.locator,
            value.display_text,
            "new",
        )
        authority = SourceFileAuthority(
            execution_id,
            0,
            repository_id,
            "direct",
            "main",
            "a" * 40,
            path,
            len(content),
            hashlib.sha256(content).hexdigest(),
        )
        slug = str(repository_id)
        files.append(CapturedFile(mapping_id, authority, replace(parser, content=b""), (edit,)))
        mappings.append(
            CapturedMapping(
                product_id=uuid4(),
                revision_id=uuid4(),
                revision_version=1,
                mapping_id=mapping_id,
                scope_id=uuid4(),
                dataset_version=1,
                import_job_id=uuid4(),
                execution_id=execution_id,
                topology="direct",
                confirmed_preview_job_id=uuid4(),
                confirmed_preview_digest="d" * 64,
                selected_layout_candidate_id=uuid4(),
                selected_layout_version=1,
                base_language="en",
                sides=(
                    CapturedSourceSide(
                        "direct", repository_id, "team", slug, "main", "a" * 40, None
                    ),
                ),
                source_references=(authority,),
                allowed_targets=(("main", True),),
            )
        )
        proposals.append(
            CapturedProposal(
                uuid4(),
                2,
                uuid4(),
                "it",
                0,
                (),
                None,
                (CapturedMember(uuid4(), 1, "e" * 64, 1, "f" * 64, authority, edit),),
            )
        )
        contents[slug, path] = content
    captured = CapturedWritebackAuthority(
        actor_id, 1, ("admin",), 1, tuple(proposals), tuple(mappings), tuple(files)
    )
    data = SimpleNamespace(
        service=service,
        factory=Factory(),
        captured=captured,
        contents=contents,
        selection=WritebackSelection(
            actor_id, tuple(ProposalSelection(p.proposal_id, p.version) for p in proposals)
        ),
    )
    monkeypatch.setattr(service, "capture_writeback_authority", lambda *a, **k: data.captured)
    monkeypatch.setattr(service, "_renewal_due", lambda session: False)
    data.adapter = ReadOnlyAdapter(data)
    return data


def prepare(data):
    return asyncio.run(
        data.service.prepare_writeback(data.factory, selection=data.selection, adapter=data.adapter)
    )


def revalidate(data, prepared):
    return asyncio.run(
        data.service.revalidate_writeback_authority(
            data.factory, prepared=prepared, adapter=data.adapter
        )
    )


def test_prepare_four_formats_is_deterministic(monkeypatch):
    data = scenario(monkeypatch)
    first = prepare(data)
    data.selection = replace(data.selection, proposals=tuple(reversed(data.selection.proposals)))
    data.captured = replace(
        data.captured,
        files=tuple(reversed(data.captured.files)),
        mappings=tuple(reversed(data.captured.mappings)),
        proposals=tuple(reversed(data.captured.proposals)),
    )
    second = prepare(data)
    assert first == second
    assert len(first.files) == 4 and len(first.manifest_digest) == 64
    assert all(b"new" in f.content and b"old" in f.original_bytes for f in first.files)
    assert "old" not in repr(first) and "new" not in repr(first)
    with pytest.raises(FrozenInstanceError):
        first.manifest_digest = "x"
    revalidate(data, first)


def test_separate_keys_side_movement_blocks(monkeypatch):
    data = scenario(monkeypatch, four=False)
    mapping = data.captured.mappings[0]
    keys = replace(
        mapping.sides[0], repository_side="keys", repository_id=uuid4(), repository_slug="keys"
    )
    reference = replace(
        mapping.source_references[0],
        repository_side="keys",
        repository_id=keys.repository_id,
        source_reference_position=1,
    )
    data.captured = replace(
        data.captured,
        mappings=(
            replace(
                mapping,
                sides=(*mapping.sides, keys),
                source_references=(*mapping.source_references, reference),
            ),
        ),
    )
    data.adapter.heads["keys"] = "b" * 40
    with pytest.raises(WritebackRejected) as error:
        prepare(data)
    assert error.value.reason == WritebackReason.SOURCE_BRANCH_CHANGED
    assert not any(call[0] == "raw" for call in data.adapter.calls)


def test_source_file_digest_mismatch_blocks(monkeypatch):
    data = scenario(monkeypatch, four=False)
    key = next(iter(data.contents))
    data.contents[key] = data.contents[key].replace(b"old", b"bad")
    with pytest.raises(WritebackRejected) as error:
        prepare(data)
    assert error.value.reason == WritebackReason.SOURCE_FILE_CHANGED


def test_branch_move_during_read_blocks(monkeypatch):
    data = scenario(monkeypatch, four=False)
    slug = data.captured.mappings[0].sides[0].repository_slug
    data.adapter.after_read = lambda: data.adapter.heads.update({slug: "b" * 40})
    with pytest.raises(WritebackRejected) as error:
        prepare(data)
    assert error.value.reason == WritebackReason.SOURCE_BRANCH_CHANGED


def test_selected_unsupported_file_blocks_entire_preparation(monkeypatch):
    data = scenario(monkeypatch)
    broken = replace(
        data.captured.files[-1],
        parser_input=replace(data.captured.files[-1].parser_input, format="xliff"),
    )
    data.captured = replace(data.captured, files=(*data.captured.files[:-1], broken))
    with pytest.raises(WritebackRejected) as error:
        prepare(data)
    assert error.value.reason == WritebackReason.UNSUPPORTED_FORMAT


def test_no_mutation_methods_are_called(monkeypatch):
    data = scenario(monkeypatch)
    prepare(data)
    assert {c[0] for c in data.adapter.calls} == {"head", "meta", "raw"}
    assert len({id(c[1]) for c in data.adapter.calls}) == len(data.adapter.calls)
    assert len([c for c in data.adapter.calls if c[0] == "head"]) == 8


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (404, WritebackReason.SOURCE_FILE_MISSING),
        (429, WritebackReason.PROVIDER_UNAVAILABLE),
        (401, WritebackReason.AUTHORITY_UNAVAILABLE),
    ],
)
def test_safe_provider_failure_mapping(monkeypatch, status, reason):
    data = scenario(monkeypatch, four=False)
    original = data.adapter.read_repository_source_file

    async def fail(*args, **kwargs):
        await original(*args, **kwargs)
        raise BitbucketProviderReadError(provider_status=status)

    data.adapter.read_repository_source_file = fail
    with pytest.raises(WritebackRejected) as error:
        prepare(data)
    assert error.value.reason == reason
    assert "Bearer" not in str(error.value)


def test_selection_count_is_bounded(monkeypatch):
    data = scenario(monkeypatch)
    monkeypatch.setattr(data.service, "MAX_CANONICAL_VALUES", 2)
    with pytest.raises(WritebackRejected) as error:
        prepare(data)
    assert error.value.reason == WritebackReason.LIMIT_EXCEEDED
    assert not data.adapter.calls


@pytest.mark.parametrize("expanded", [False, True])
def test_aggregate_file_bytes_are_bounded(monkeypatch, expanded):
    data = scenario(monkeypatch)
    input_bytes = sum(len(v) for v in data.contents.values())
    monkeypatch.setattr(
        data.service,
        "MAX_CANONICAL_AGGREGATE_BYTES",
        input_bytes + 20 if expanded else input_bytes - 1,
    )
    if expanded:
        # Keep cumulative selected text beneath the input budget, but the XML
        # output escaping expands beyond it across individually small files.
        files = tuple(
            replace(f, edits=tuple(replace(e, replacement_text="&" * 40) for e in f.edits))
            for f in data.captured.files
        )
        data.captured = replace(
            data.captured,
            files=files,
            proposals=tuple(
                replace(
                    p,
                    members=tuple(
                        replace(m, edit=replace(m.edit, replacement_text="&" * 40))
                        for m in p.members
                    ),
                )
                for p in data.captured.proposals
            ),
        )
    with pytest.raises(WritebackRejected) as error:
        prepare(data)
    assert error.value.reason == WritebackReason.LIMIT_EXCEEDED
    assert any(call[0] == "raw" for call in data.adapter.calls) is expanded


@pytest.mark.parametrize(
    "change", [{"size_bytes": 999}, {"attributes": ("link",)}, {"commit_hash": "b" * 40}]
)
def test_metadata_refusal_precedes_raw_read(monkeypatch, change):
    data = scenario(monkeypatch, four=False)
    original = data.adapter.read_repository_source_metadata

    async def altered(*args, **kwargs):
        return replace(await original(*args, **kwargs), **change)

    data.adapter.read_repository_source_metadata = altered
    with pytest.raises(WritebackRejected):
        prepare(data)
    assert not any(call[0] == "raw" for call in data.adapter.calls)


def test_revalidation_repeats_manifest_byte_bound_before_provider_reads(monkeypatch):
    data = scenario(monkeypatch, four=False)
    prepared = prepare(data)
    data.adapter.calls.clear()
    monkeypatch.setattr(data.service, "MAX_CANONICAL_MAPPING_OUTPUT_BYTES", 100)
    with pytest.raises(WritebackRejected) as error:
        revalidate(data, prepared)
    assert error.value.reason == WritebackReason.LIMIT_EXCEEDED
    assert not data.adapter.calls


def test_local_change_during_io_is_refused(monkeypatch):
    data = scenario(monkeypatch, four=False)
    data.adapter.after_read = lambda: setattr(
        data, "captured", replace(data.captured, actor_token_version=2)
    )
    with pytest.raises(WritebackRejected) as error:
        prepare(data)
    assert error.value.reason == WritebackReason.STALE_BASIS


def test_healthy_generation_change_during_bootstrap_is_refused(monkeypatch):
    data = scenario(monkeypatch, four=False)
    original = data.adapter.resolve_repository_branch

    async def replaced_connection(*args, **kwargs):
        branch = await original(*args, **kwargs)
        data.captured = replace(data.captured, connection_generation=2)
        return branch

    data.adapter.resolve_repository_branch = replaced_connection
    with pytest.raises(WritebackRejected) as error:
        prepare(data)
    assert error.value.reason == WritebackReason.STALE_BASIS


@pytest.mark.parametrize("change", ["digest", "text", "bytes", "version"])
def test_manifest_forgery_is_refused(monkeypatch, change):
    data = scenario(monkeypatch, four=False)
    prepared = prepare(data)
    if change == "digest":
        prepared = replace(prepared, manifest_digest="0" * 64)
    elif change == "version":
        prepared = replace(prepared, manifest_version=2)
    elif change == "text":
        member = prepared.authority.proposals[0].members[0]
        proposal = replace(
            prepared.authority.proposals[0],
            members=(replace(member, edit=replace(member.edit, replacement_text="forged")),),
        )
        prepared = replace(prepared, authority=replace(prepared.authority, proposals=(proposal,)))
    else:
        file = prepared.files[0]
        content = file.content.replace(b"new", b"bad")
        prepared = replace(
            prepared,
            files=(
                replace(file, content=content, after_sha256=hashlib.sha256(content).hexdigest()),
            ),
        )
    data.adapter.calls.clear()
    with pytest.raises(WritebackRejected) as error:
        revalidate(data, prepared)
    assert error.value.reason == WritebackReason.STALE_BASIS
    assert not data.adapter.calls


def test_manifest_with_recomputed_forged_digest_is_refused(monkeypatch):
    data = scenario(monkeypatch, four=False)
    prepared = prepare(data)
    altered = replace(
        prepared.files[0],
        content=prepared.files[0].original_bytes,
        after_sha256=prepared.files[0].before_sha256,
        changed_edits=(),
    )
    prepared = replace(prepared, files=(altered,))
    prepared = replace(prepared, manifest_digest=data.service._manifest_digest(prepared))
    with pytest.raises(WritebackRejected) as error:
        revalidate(data, prepared)
    assert error.value.reason == WritebackReason.STALE_BASIS


def test_all_noop_still_has_complete_manifest(monkeypatch):
    data = scenario(monkeypatch, four=False)
    file = data.captured.files[0]
    noop = replace(file.edits[0], replacement_text=file.edits[0].expected_text)
    proposal = data.captured.proposals[0]
    data.captured = replace(
        data.captured,
        files=(replace(file, edits=(noop,)),),
        proposals=(replace(proposal, members=(replace(proposal.members[0], edit=noop),)),),
    )
    prepared = prepare(data)
    assert len(prepared.authority.proposals[0].members) == 1
    assert len(prepared.files) == 1
    assert prepared.files[0].content == prepared.files[0].original_bytes
    assert prepared.files[0].changed_edits == ()
    revalidate(data, prepared)


@pytest.mark.parametrize("conflict", [False, True])
def test_physical_file_consolidation_retains_each_mapping(monkeypatch, conflict):
    data = scenario(monkeypatch, four=False)
    file = data.captured.files[0]
    mapping = replace(
        data.captured.mappings[0], mapping_id=uuid4(), product_id=uuid4(), scope_id=uuid4()
    )
    duplicate = replace(file, mapping_id=mapping.mapping_id)
    if conflict:
        duplicate = replace(
            duplicate, edits=(replace(duplicate.edits[0], replacement_text="contradiction"),)
        )
    data.captured = replace(
        data.captured,
        mappings=(*data.captured.mappings, mapping),
        files=(*data.captured.files, duplicate),
    )
    if conflict:
        with pytest.raises(WritebackRejected) as error:
            prepare(data)
        assert error.value.reason == WritebackReason.AMBIGUOUS_LOCATOR
    else:
        prepared = prepare(data)
        assert len(prepared.files) == 1 and len(prepared.authority.mappings) == 2
        assert len(prepared.files[0].changed_edits) == 1


def test_conflicting_parser_authority_on_same_file_is_refused(monkeypatch):
    data = scenario(monkeypatch, four=False)
    mapping = replace(data.captured.mappings[0], mapping_id=uuid4())
    duplicate = replace(
        data.captured.files[0],
        mapping_id=mapping.mapping_id,
        parser_input=replace(data.captured.files[0].parser_input, base_language="de"),
    )
    data.captured = replace(
        data.captured,
        mappings=(*data.captured.mappings, mapping),
        files=(*data.captured.files, duplicate),
    )
    with pytest.raises(WritebackRejected) as error:
        prepare(data)
    assert error.value.reason == WritebackReason.AMBIGUOUS_LOCATOR
