"""Closed version-1 JSON codec for private frozen writeback proofs.

Only the fixed dataclasses below are reconstructible. Limits are checked before
base64 decoding, and declared field types are checked without coercion. This
codec preserves proof identity; it never grants authority (revalidation does).
"""

import base64
import hashlib
import json
from dataclasses import fields
from types import UnionType
from typing import Any, Literal, TypeAliasType, get_args, get_origin, get_type_hints
from uuid import UUID

from verboflex.localization.importing.core import (
    MAX_CANONICAL_AGGREGATE_BYTES,
    MAX_CANONICAL_FILE_BYTES,
    MAX_CANONICAL_MAPPING_OUTPUT_BYTES,
    CanonicalLocator,
    CanonicalParserInput,
    CanonicalSelector,
)
from verboflex.localization.writing.core import (
    RenderedFile,
    SourceFileAuthority,
    WriteEdit,
    WriteInsert,
)
from verboflex.schemas.submissions import MappingTarget
from verboflex.services.submission_selection import (
    PreparedSubmissionGroup,
    PreparedSubmissionReview,
    enforce_review_bounds,
    partition_selection,
    review_content_digest,
)
from verboflex.services.writeback import PreparedWriteback, ProposalSelection, WritebackSelection
from verboflex.services.writeback_authority import (
    CapturedConstraint,
    CapturedFile,
    CapturedMapping,
    CapturedMember,
    CapturedProposal,
    CapturedSourceSide,
    CapturedWritebackAuthority,
)

_RECORDS = (
    PreparedSubmissionGroup,
    PreparedSubmissionReview,
    PreparedWriteback,
    ProposalSelection,
    WritebackSelection,
    CapturedWritebackAuthority,
    CapturedProposal,
    CapturedMember,
    CapturedConstraint,
    CapturedMapping,
    CapturedSourceSide,
    CapturedFile,
    RenderedFile,
    SourceFileAuthority,
    WriteEdit,
    WriteInsert,
    CanonicalParserInput,
    CanonicalSelector,
    CanonicalLocator,
)
_TYPES = {cls.__name__: cls for cls in _RECORDS}
_HINTS = {cls: get_type_hints(cls) for cls in _RECORDS}
MAX_PAYLOAD_BYTES = MAX_CANONICAL_MAPPING_OUTPUT_BYTES


def _invalid() -> ValueError:
    return ValueError("prepared review payload rejected")


def _matches(value: object, annotation: Any) -> bool:
    if isinstance(annotation, TypeAliasType):
        return _matches(value, annotation.__value__)
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is UnionType:
        return any(_matches(value, option) for option in args)
    if origin is Literal:
        return any(type(value) is type(option) and value == option for option in args)
    if origin is tuple:
        if type(value) is not tuple:
            return False
        if len(args) == 2 and args[1] is Ellipsis:
            return all(_matches(item, args[0]) for item in value)
        return len(value) == len(args) and all(
            _matches(v, a) for v, a in zip(value, args, strict=True)
        )
    return type(value) is annotation


class _Budget:
    def __init__(self) -> None:
        self.nodes = 0
        self.binary = 0
        self.text = 0

    def visit(self, depth: int) -> None:
        self.nodes += 1
        if depth > 40 or self.nodes > 500_000:
            raise _invalid()

    def bytes(self, size: int) -> None:
        self.binary += size
        if size > MAX_CANONICAL_FILE_BYTES or self.binary > 2 * MAX_CANONICAL_AGGREGATE_BYTES:
            raise _invalid()


def _encode(value: Any, budget: _Budget, depth: int = 0) -> Any:
    budget.visit(depth)
    if type(value) in _HINTS:
        if not all(
            _matches(getattr(value, f.name), _HINTS[type(value)][f.name]) for f in fields(value)
        ):
            raise _invalid()
        return {
            "record": type(value).__name__,
            "fields": {
                f.name: _encode(getattr(value, f.name), budget, depth + 1) for f in fields(value)
            },
        }
    if type(value) is tuple:
        if len(value) > 5000:
            raise _invalid()
        return {"tuple": [_encode(item, budget, depth + 1) for item in value]}
    if type(value) is UUID:
        return {"uuid": str(value)}
    if type(value) is bytes:
        budget.bytes(len(value))
        return {"bytes": base64.b64encode(value).decode("ascii")}
    if type(value) is str:
        size = len(value.encode("utf-8"))
        budget.text += size
        if size > MAX_CANONICAL_FILE_BYTES or budget.text > MAX_PAYLOAD_BYTES:
            raise _invalid()
        return value
    if (
        value is None
        or type(value) is bool
        or (type(value) is int and abs(value) <= 9_007_199_254_740_991)
    ):
        return value
    raise _invalid()


def _decode(value: Any, budget: _Budget, depth: int = 0) -> Any:
    budget.visit(depth)
    if type(value) is dict:
        if set(value) == {"record", "fields"} and type(value["record"]) is str:
            cls = _TYPES.get(value["record"])
            if (
                cls is None
                or type(value["fields"]) is not dict
                or set(value["fields"]) != set(_HINTS[cls])
            ):
                raise _invalid()
            decoded = {
                name: _decode(item, budget, depth + 1) for name, item in value["fields"].items()
            }
            if not all(_matches(item, _HINTS[cls][name]) for name, item in decoded.items()):
                raise _invalid()
            return cls(**decoded)
        if set(value) == {"tuple"} and type(value["tuple"]) is list and len(value["tuple"]) <= 5000:
            return tuple(_decode(item, budget, depth + 1) for item in value["tuple"])
        if set(value) == {"uuid"} and type(value["uuid"]) is str and len(value["uuid"]) == 36:
            return UUID(value["uuid"])
        if set(value) == {"bytes"} and type(value["bytes"]) is str:
            encoded = value["bytes"]
            if len(encoded) % 4 or len(encoded) > 4 * ((MAX_CANONICAL_FILE_BYTES + 2) // 3):
                raise _invalid()
            size = len(encoded) // 4 * 3 - (len(encoded) - len(encoded.rstrip("=")))
            budget.bytes(size)
            result = base64.b64decode(encoded, validate=True)
            if len(result) != size or base64.b64encode(result).decode("ascii") != encoded:
                raise _invalid()
            return result
        raise _invalid()
    return _encode(value, budget, depth)


def _proof(value: Any) -> PreparedWriteback:
    if type(value) is not PreparedWriteback or value.manifest_version != 1 or not value.files:
        raise _invalid()
    if len(value.manifest_digest) != 64 or any(
        c not in "0123456789abcdef" for c in value.manifest_digest
    ):
        raise _invalid()
    if len(value.files) > 500 or len(value.authority.proposals) > 5000:
        raise _invalid()
    if (
        sum(len(f.original_bytes) for f in value.files) > MAX_CANONICAL_AGGREGATE_BYTES
        or sum(len(f.content) for f in value.files) > MAX_CANONICAL_AGGREGATE_BYTES
        or sum(len(p.members) for p in value.authority.proposals) > 5000
    ):
        raise _invalid()
    for file in value.files:
        if (
            hashlib.sha256(file.original_bytes).hexdigest() != file.before_sha256
            or hashlib.sha256(file.content).hexdigest() != file.after_sha256
            or file.authority.sha256 != file.before_sha256
        ):
            raise _invalid()
    return value


def encode_prepared_writeback(prepared: PreparedWriteback) -> bytes:
    try:
        value = {"version": 1, "prepared": _encode(_proof(prepared), _Budget())}
        chunks = json.JSONEncoder(ensure_ascii=True, separators=(",", ":")).iterencode(value)
        output = bytearray()
        for chunk in chunks:
            encoded = chunk.encode("ascii")
            if len(output) + len(encoded) > MAX_PAYLOAD_BYTES:
                raise _invalid()
            output.extend(encoded)
        return bytes(output)
    except ValueError, TypeError, AttributeError, RecursionError:
        raise _invalid() from None


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _invalid()
        result[key] = value
    return result


def decode_prepared_writeback(payload: bytes) -> PreparedWriteback:
    try:
        if type(payload) is not bytes or len(payload) > MAX_PAYLOAD_BYTES:
            raise _invalid()
        envelope = json.loads(payload, object_pairs_hook=_unique)
        if (
            type(envelope) is not dict
            or set(envelope) != {"version", "prepared"}
            or type(envelope["version"]) is not int
            or envelope["version"] != 1
        ):
            raise _invalid()
        return _proof(_decode(envelope["prepared"], _Budget()))
    except ValueError, TypeError, AttributeError, RecursionError, KeyError:
        raise _invalid() from None


def _review_proof(value: Any) -> PreparedSubmissionReview:
    if type(value) is not PreparedSubmissionReview or value.version != 1:
        raise _invalid()
    enforce_review_bounds(value.groups)
    if value.content_digest != review_content_digest(value.groups):
        raise _invalid()
    keys = [(g.repository_id, g.target_branch) for g in value.groups]
    if keys != sorted(set(keys)):
        raise _invalid()
    for group in value.groups:
        _proof(group.prepared)
        partition = partition_selection(
            group.prepared.authority,
            targets=tuple(
                MappingTarget(mapping_id=m.mapping_id, target_branch=group.target_branch)
                for m in group.prepared.authority.mappings
            ),
        )
        if len(partition) != 1 or (
            partition[0].repository_id,
            partition[0].workspace,
            partition[0].repository_slug,
            partition[0].target_branch,
        ) != (group.repository_id, group.workspace, group.repository_slug, group.target_branch):
            raise _invalid()
        if len(group.target_head) != 40 or any(
            c not in "0123456789abcdef" for c in group.target_head
        ):
            raise _invalid()
    return value


def encode_submission_review(review: PreparedSubmissionReview) -> bytes:
    try:
        value = {"version": 1, "review": _encode(_review_proof(review), _Budget())}
        output = bytearray()
        for chunk in json.JSONEncoder(ensure_ascii=True, separators=(",", ":")).iterencode(value):
            encoded = chunk.encode("ascii")
            if len(output) + len(encoded) > MAX_PAYLOAD_BYTES:
                raise _invalid()
            output.extend(encoded)
        return bytes(output)
    except ValueError, TypeError, AttributeError, RecursionError:
        raise _invalid() from None


def decode_submission_review(payload: bytes) -> PreparedSubmissionReview:
    try:
        if type(payload) is not bytes or len(payload) > MAX_PAYLOAD_BYTES:
            raise _invalid()
        envelope = json.loads(payload, object_pairs_hook=_unique)
        if (
            type(envelope) is not dict
            or set(envelope) != {"version", "review"}
            or type(envelope["version"]) is not int
            or envelope["version"] != 1
        ):
            raise _invalid()
        return _review_proof(_decode(envelope["review"], _Budget()))
    except ValueError, TypeError, AttributeError, RecursionError, KeyError:
        raise _invalid() from None
