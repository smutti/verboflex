"""Fail-closed construction and validation for Bitbucket Cloud REST URLs."""

from __future__ import annotations

import json
import re
from enum import StrEnum
from urllib.parse import parse_qs, quote, unquote, urlencode, urlsplit
from uuid import UUID

BITBUCKET_API_HOST = "api.bitbucket.org"
BITBUCKET_API_ORIGIN = f"https://{BITBUCKET_API_HOST}"
BITBUCKET_URL_REJECTED_MESSAGE = "Bitbucket provider URL rejected"
BITBUCKET_OPERATION_REJECTED_MESSAGE = "Bitbucket provider operation rejected"


class BitbucketOperation(StrEnum):
    """Application-owned Bitbucket operation vocabulary across Phases 3 and 8."""

    WORKSPACE_REPOSITORIES = "workspace-repository-list"
    REPOSITORY_METADATA = "repository-metadata-by-workspace-and-slug"
    BRANCH_LIST = "branch-listing-with-provider-pagination"
    BRANCH_RESOLVE = "branch-to-commit-resolution"
    COMMIT_ANCESTRY = "commit-ancestry-comparison"
    COMMIT_DIFFSTAT = "commit-diffstat-between-source-commits"
    SOURCE_TREE = "source-tree-directory-pagination"
    SOURCE_FILE = "raw-source-file-read-at-commit"
    SOURCE_METADATA = "source-file-metadata-at-commit"
    BRANCH_CREATE = "branch-create"
    SOURCE_COMMIT_CREATE = "source-commit-create"
    PULL_REQUEST_CREATE = "pull-request-create"


PHASE_3_READ_OPERATIONS = frozenset(
    {
        BitbucketOperation.WORKSPACE_REPOSITORIES,
        BitbucketOperation.REPOSITORY_METADATA,
        BitbucketOperation.BRANCH_LIST,
        BitbucketOperation.BRANCH_RESOLVE,
        BitbucketOperation.COMMIT_ANCESTRY,
        BitbucketOperation.COMMIT_DIFFSTAT,
        BitbucketOperation.SOURCE_TREE,
        BitbucketOperation.SOURCE_FILE,
        BitbucketOperation.SOURCE_METADATA,
    }
)
PHASE_8_WRITE_OPERATIONS = frozenset(
    {
        BitbucketOperation.BRANCH_CREATE,
        BitbucketOperation.SOURCE_COMMIT_CREATE,
        BitbucketOperation.PULL_REQUEST_CREATE,
    }
)

_PROVIDER_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9_-]{0,99}")
_ENCODED_PATH_SEGMENT = r"(?:[A-Za-z0-9._~-]|%[0-9A-Fa-f]{2})+"
_REPOSITORY_READ_BASE = rf"/2\.0/repositories/{_ENCODED_PATH_SEGMENT}/{_ENCODED_PATH_SEGMENT}"
_REPOSITORY_METADATA_PATH = re.compile(rf"{_REPOSITORY_READ_BASE}/?")
_BRANCH_LIST_PATH = re.compile(rf"{_REPOSITORY_READ_BASE}/refs/branches/?")
_BRANCH_RESOLVE_PATH = re.compile(
    rf"{_REPOSITORY_READ_BASE}/refs/branches/{_ENCODED_PATH_SEGMENT}/?"
)
_COMMIT_HASH = r"[0-9A-Fa-f]{40}"
_COMMIT_ANCESTRY_PATH = re.compile(rf"{_REPOSITORY_READ_BASE}/commits/{_COMMIT_HASH}/?")
_COMMIT_DIFFSTAT_PATH = re.compile(
    rf"{_REPOSITORY_READ_BASE}/diffstat/{_COMMIT_HASH}\.\.{_COMMIT_HASH}/?"
)
_SOURCE_PATH = re.compile(
    rf"{_REPOSITORY_READ_BASE}/src/{_COMMIT_HASH}"
    rf"(?:/{_ENCODED_PATH_SEGMENT}(?:/{_ENCODED_PATH_SEGMENT})*)?/?"
)
_SOURCE_METADATA_PATH = re.compile(
    rf"{_REPOSITORY_READ_BASE}/src/{_COMMIT_HASH}"
    rf"/{_ENCODED_PATH_SEGMENT}(?:/{_ENCODED_PATH_SEGMENT})*"
)
_READ_PATHS_BY_OPERATION: dict[BitbucketOperation, tuple[re.Pattern[str], ...]] = {
    BitbucketOperation.WORKSPACE_REPOSITORIES: (
        re.compile(rf"/2\.0/repositories/{_ENCODED_PATH_SEGMENT}/?"),
    ),
    BitbucketOperation.REPOSITORY_METADATA: (_REPOSITORY_METADATA_PATH,),
    BitbucketOperation.BRANCH_LIST: (_BRANCH_LIST_PATH,),
    BitbucketOperation.BRANCH_RESOLVE: (_BRANCH_RESOLVE_PATH,),
    BitbucketOperation.SOURCE_TREE: (_SOURCE_PATH,),
    BitbucketOperation.SOURCE_FILE: (_SOURCE_PATH,),
    BitbucketOperation.SOURCE_METADATA: (_SOURCE_METADATA_PATH,),
    BitbucketOperation.COMMIT_ANCESTRY: (_COMMIT_ANCESTRY_PATH,),
    BitbucketOperation.COMMIT_DIFFSTAT: (_COMMIT_DIFFSTAT_PATH,),
}
_ALLOWED_READ_PATHS = tuple(
    pattern for patterns in _READ_PATHS_BY_OPERATION.values() for pattern in patterns
)


def _source_path_is_safe(path: str) -> bool:
    marker = "/src/"
    if marker not in path:
        return True
    suffix = path.split(marker, 1)[1]
    parts = suffix.split("/")[1:]
    for encoded_part in parts:
        if not encoded_part:
            continue
        decoded_part = unquote(encoded_part)
        if (
            decoded_part in {".", ".."}
            or "/" in decoded_part
            or "\\" in decoded_part
            or "\x00" in decoded_part
            or not decoded_part.isprintable()
        ):
            return False
    return True


def validate_bitbucket_api_url(
    url: str,
    *,
    operation: BitbucketOperation | None = None,
) -> str:
    """Return one exact Bitbucket REST URL or reject it before authentication."""
    if operation is not None and (
        not isinstance(operation, BitbucketOperation) or operation not in PHASE_3_READ_OPERATIONS
    ):
        raise ValueError(BITBUCKET_OPERATION_REJECTED_MESSAGE)
    if not isinstance(url, str) or not url or "\\" in url:
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE) from None
    if (
        parsed.scheme != "https"
        or parsed.hostname != BITBUCKET_API_HOST
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or not any(
            pattern.fullmatch(parsed.path)
            for pattern in (
                _READ_PATHS_BY_OPERATION.get(operation, ())
                if operation is not None
                else _ALLOWED_READ_PATHS
            )
        )
        or not _source_path_is_safe(parsed.path)
        or parsed.fragment
        or (operation is BitbucketOperation.SOURCE_METADATA and parsed.query != "format=meta")
    ):
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    return url


def repository_source_metadata_url(
    *, workspace: str, repository_slug: str, commit_hash: str, path: str
) -> str:
    """Build only the exact immutable file metadata projection."""
    source = repository_source_url(
        workspace=workspace, repository_slug=repository_slug, commit_hash=commit_hash, path=path
    )
    return validate_bitbucket_api_url(
        f"{source}?format=meta", operation=BitbucketOperation.SOURCE_METADATA
    )


def repository_metadata_url(*, workspace: str, repository_slug: str) -> str:
    """Build the only repository metadata endpoint accepted by the tracer."""
    if (
        _PROVIDER_IDENTIFIER.fullmatch(workspace) is None
        or _PROVIDER_IDENTIFIER.fullmatch(repository_slug) is None
    ):
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    url = (
        f"{BITBUCKET_API_ORIGIN}/2.0/repositories/"
        f"{quote(workspace, safe='')}/{quote(repository_slug, safe='')}"
    )
    return validate_bitbucket_api_url(url, operation=BitbucketOperation.REPOSITORY_METADATA)


def repository_branches_url(*, workspace: str, repository_slug: str) -> str:
    """Build the live branch collection with Bitbucket's maximum page size."""
    base = repository_metadata_url(workspace=workspace, repository_slug=repository_slug)
    return validate_bitbucket_api_url(
        f"{base}/refs/branches?{urlencode({'pagelen': 100})}",
        operation=BitbucketOperation.BRANCH_LIST,
    )


def repository_branch_url(
    *,
    workspace: str,
    repository_slug: str,
    branch: str,
) -> str:
    """Build one exact branch-detail endpoint without interpreting its spelling."""
    if (
        not isinstance(branch, str)
        or not branch
        or len(branch) > 255
        or "\\" in branch
        or "\x00" in branch
        or not branch.isprintable()
    ):
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    base = repository_branches_url(
        workspace=workspace,
        repository_slug=repository_slug,
    ).split("?", 1)[0]
    return validate_bitbucket_api_url(
        f"{base}/{quote(branch, safe='')}",
        operation=BitbucketOperation.BRANCH_RESOLVE,
    )


def validate_repository_relative_path(path: str) -> str:
    """Return one printable repository-relative POSIX path without traversal."""
    if (
        not isinstance(path, str)
        or not path
        or len(path) > 4096
        or path.startswith("/")
        or path.endswith("/")
        or "\\" in path
        or "\x00" in path
        or not path.isprintable()
    ):
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    parts = path.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    return "/".join(parts)


def validate_localization_root(path: str) -> str:
    """Require an exact raw directory, never an encoded traversal alias."""
    validated = validate_repository_relative_path(path)
    if unquote(validated) != validated:
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    return validated


def validate_provider_commit_hash(commit_hash: str) -> str:
    """Return one full provider commit hash without accepting symbolic revisions."""
    if (
        not isinstance(commit_hash, str)
        or len(commit_hash) != 40
        or any(character not in "0123456789abcdefABCDEF" for character in commit_hash)
    ):
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    return commit_hash


def repository_commit_ancestry_url(
    *,
    workspace: str,
    repository_slug: str,
    old_commit_hash: str,
    new_commit_hash: str,
) -> str:
    """Build the exact proposed-commit history used for bounded reachability."""
    validate_provider_commit_hash(old_commit_hash)
    proposed = validate_provider_commit_hash(new_commit_hash)
    base = repository_metadata_url(workspace=workspace, repository_slug=repository_slug)
    return validate_bitbucket_api_url(
        f"{base}/commits/{proposed}?{urlencode({'pagelen': 100})}",
        operation=BitbucketOperation.COMMIT_ANCESTRY,
    )


def repository_diffstat_url(
    *,
    workspace: str,
    repository_slug: str,
    old_commit_hash: str,
    new_commit_hash: str,
) -> str:
    """Build a two-commit diffstat from proposed state to the prior baseline."""
    previous = validate_provider_commit_hash(old_commit_hash)
    proposed = validate_provider_commit_hash(new_commit_hash)
    base = repository_metadata_url(workspace=workspace, repository_slug=repository_slug)
    query = urlencode({"pagelen": 100, "renames": "false", "topic": "false"})
    return validate_bitbucket_api_url(
        f"{base}/diffstat/{proposed}..{previous}?{query}",
        operation=BitbucketOperation.COMMIT_DIFFSTAT,
    )


def repository_source_url(
    *,
    workspace: str,
    repository_slug: str,
    commit_hash: str,
    path: str | None = None,
    paginated: bool = False,
    max_depth: int | None = None,
) -> str:
    """Build one commit-bound source tree or raw-file endpoint."""
    validate_provider_commit_hash(commit_hash)
    base = repository_metadata_url(workspace=workspace, repository_slug=repository_slug)
    url = f"{base}/src/{commit_hash}/"
    if path is not None:
        encoded_path = "/".join(
            quote(part, safe="") for part in validate_repository_relative_path(path).split("/")
        )
        url = f"{url}{encoded_path}"
    if max_depth is not None and (
        not paginated or isinstance(max_depth, bool) or not 1 <= max_depth <= 100
    ):
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    if paginated:
        query: dict[str, int] = {"pagelen": 100}
        if max_depth is not None:
            query["max_depth"] = max_depth
        url = f"{url}?{urlencode(query)}"
    operation = BitbucketOperation.SOURCE_TREE if paginated else BitbucketOperation.SOURCE_FILE
    return validate_bitbucket_api_url(url, operation=operation)


def workspace_repositories_url(*, workspace: str, query: str = "", limit: int = 20) -> str:
    """Build one bounded repository search in the administrator-selected workspace."""
    if _PROVIDER_IDENTIFIER.fullmatch(workspace) is None or not 1 <= limit <= 50:
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    if len(query) > 100 or (query and not query.isprintable()):
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    parameters: dict[str, str | int] = {"pagelen": limit, "sort": "name"}
    if query:
        literal = json.dumps(query, ensure_ascii=False)
        parameters["q"] = f"name ~ {literal} OR slug ~ {literal}"
    return validate_bitbucket_api_url(
        f"{BITBUCKET_API_ORIGIN}/2.0/repositories/{workspace}?{urlencode(parameters)}",
        operation=BitbucketOperation.WORKSPACE_REPOSITORIES,
    )


class BitbucketWriteOperation(StrEnum):
    """Separate narrow write/recovery vocabulary; the read facade stays GET-only."""

    CREATE_BRANCH = "create-owned-branch"
    CREATE_COMMIT = "create-conditional-commit"
    READ_REPOSITORY = "read-write-repository-identity"
    READ_BRANCH = "read-owned-branch"
    READ_COMMIT = "read-exact-commit"
    RESOLVE_PR_COMMIT = "resolve-pull-request-commit-prefix"
    READ_DIFFSTAT = "read-exact-commit-diffstat"
    READ_FILE = "read-written-file"
    READ_METADATA = "read-written-file-metadata"
    CREATE_PULL_REQUEST = "create-exact-pull-request"
    READ_PULL_REQUEST = "read-exact-pull-request"
    READ_MERGEABILITY = "read-pull-request-mergeability"
    LIST_PULL_REQUESTS = "reconcile-all-state-pull-requests"


def repository_write_base_url(*, workspace: str, repository_id: UUID) -> str:
    """Address immutable repository identity even if a slug is concurrently reused."""
    if (
        not isinstance(workspace, str)
        or _PROVIDER_IDENTIFIER.fullmatch(workspace) is None
        or type(repository_id) is not UUID
    ):
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    identity = quote("{" + str(repository_id) + "}", safe="")
    return f"{BITBUCKET_API_ORIGIN}/2.0/repositories/{workspace}/{identity}"


_WRITE_PATHS: dict[BitbucketWriteOperation, tuple[str, re.Pattern[str]]] = {
    BitbucketWriteOperation.READ_REPOSITORY: ("GET", _REPOSITORY_METADATA_PATH),
    BitbucketWriteOperation.CREATE_BRANCH: ("POST", _BRANCH_LIST_PATH),
    BitbucketWriteOperation.CREATE_COMMIT: ("POST", re.compile(rf"{_REPOSITORY_READ_BASE}/src")),
    BitbucketWriteOperation.READ_BRANCH: ("GET", _BRANCH_RESOLVE_PATH),
    BitbucketWriteOperation.READ_COMMIT: (
        "GET",
        re.compile(rf"{_REPOSITORY_READ_BASE}/commit/{_COMMIT_HASH}"),
    ),
    BitbucketWriteOperation.RESOLVE_PR_COMMIT: (
        "GET",
        re.compile(rf"{_REPOSITORY_READ_BASE}/commit/[0-9a-f]{{12,39}}"),
    ),
    BitbucketWriteOperation.READ_DIFFSTAT: ("GET", _COMMIT_DIFFSTAT_PATH),
    BitbucketWriteOperation.READ_FILE: ("GET", _SOURCE_METADATA_PATH),
    BitbucketWriteOperation.READ_METADATA: ("GET", _SOURCE_METADATA_PATH),
    BitbucketWriteOperation.CREATE_PULL_REQUEST: (
        "POST",
        re.compile(rf"{_REPOSITORY_READ_BASE}/pullrequests"),
    ),
    BitbucketWriteOperation.READ_PULL_REQUEST: (
        "GET",
        re.compile(rf"{_REPOSITORY_READ_BASE}/pullrequests/[1-9][0-9]{{0,18}}"),
    ),
    BitbucketWriteOperation.READ_MERGEABILITY: (
        "GET",
        re.compile(rf"{_REPOSITORY_READ_BASE}/pullrequests/[1-9][0-9]{{0,18}}/mergeability/checks"),
    ),
    BitbucketWriteOperation.LIST_PULL_REQUESTS: (
        "GET",
        re.compile(rf"{_REPOSITORY_READ_BASE}/pullrequests"),
    ),
}


def validate_bitbucket_write_url(
    url: str, *, operation: BitbucketWriteOperation, method: str, expected_url: str
) -> str:
    """Bind origin, operation and exact caller-owned resource before credentials."""
    if type(operation) is not BitbucketWriteOperation or operation not in _WRITE_PATHS:
        raise ValueError(BITBUCKET_OPERATION_REJECTED_MESSAGE)
    expected_method, pattern = _WRITE_PATHS[operation]
    if method != expected_method:
        raise ValueError(BITBUCKET_OPERATION_REJECTED_MESSAGE)
    for candidate in (url, expected_url):
        if not isinstance(candidate, str) or "\\" in candidate:
            raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
        try:
            parsed = urlsplit(candidate)
            if (
                parsed.scheme != "https"
                or parsed.netloc != BITBUCKET_API_HOST
                or parsed.port is not None
                or parsed.fragment
                or not pattern.fullmatch(parsed.path)
                or not _source_path_is_safe(parsed.path)
            ):
                raise ValueError
        except ValueError:
            raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE) from None
    actual, expected = urlsplit(url), urlsplit(expected_url)
    if actual.path != expected.path:
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    if operation is BitbucketWriteOperation.LIST_PULL_REQUESTS:
        query = parse_qs(actual.query, keep_blank_values=True)
        expected_query = parse_qs(expected.query, keep_blank_values=True)
        if (
            set(query) - {"pagelen", "state", "q", "page"}
            or query.get("pagelen") != ["50"]
            or len(query.get("state", [])) != 4
            or set(query.get("state", [])) != {"OPEN", "MERGED", "DECLINED", "SUPERSEDED"}
            or query.get("q") != expected_query.get("q")
            or len(query.get("q", [])) != 1
            or (
                "page" in query
                and (
                    len(query["page"]) != 1
                    or not query["page"][0].isascii()
                    or not query["page"][0].isdecimal()
                    or len(query["page"][0]) > 2
                    or not 1 <= int(query["page"][0]) <= 50
                )
            )
        ):
            raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    elif operation is BitbucketWriteOperation.READ_DIFFSTAT:
        query = parse_qs(actual.query, keep_blank_values=True)
        if (
            set(query) - {"pagelen", "renames", "topic", "page"}
            or query.get("pagelen") != ["100"]
            or query.get("renames") != ["false"]
            or query.get("topic") != ["false"]
            or (
                "page" in query
                and (
                    len(query["page"]) != 1
                    or not query["page"][0].isascii()
                    or not query["page"][0].isdecimal()
                    or not 1 <= int(query["page"][0]) <= 50
                )
            )
        ):
            raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    elif actual.query != (
        "format=meta" if operation is BitbucketWriteOperation.READ_METADATA else ""
    ):
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    return url


def validate_pull_request_url(
    url: str, *, workspace: str, repository_slug: str, pull_request_id: int
) -> str:
    """Public navigation is exact HTTPS HTML, never provider-supplied arbitrary HTML."""
    repository_metadata_url(workspace=workspace, repository_slug=repository_slug)
    if type(pull_request_id) is not int or not 1 <= pull_request_id <= 9_007_199_254_740_991:
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    expected = (
        f"https://bitbucket.org/{workspace}/{repository_slug}/pull-requests/{pull_request_id}"
    )
    if not isinstance(url, str) or url != expected:
        raise ValueError(BITBUCKET_URL_REJECTED_MESSAGE)
    return url
