"""The write facade cannot regain ambient methods, destinations or traversal."""

import pytest

from verboflex.integrations.bitbucket.urls import (
    BitbucketWriteOperation as Operation,
)
from verboflex.integrations.bitbucket.urls import (
    validate_bitbucket_write_url,
    validate_pull_request_url,
)

BRANCH = "https://api.bitbucket.org/2.0/repositories/acme/mobile/refs/branches"


@pytest.mark.parametrize(
    "url",
    [
        BRANCH.replace("https:", "http:"),
        BRANCH.replace("api.bitbucket.org", "evil.example"),
        BRANCH.replace("api.bitbucket.org", "api.bitbucket.org.evil.example"),
        BRANCH.replace("api.bitbucket.org", "user:secret@api.bitbucket.org"),
        BRANCH.replace("api.bitbucket.org", "api.bitbucket.org:443"),
        BRANCH + "#secret",
        BRANCH + "?q=anything",
        BRANCH.replace("mobile", "other"),
        BRANCH.replace("/refs/branches", "/pullrequests"),
        BRANCH + "/../tags",
    ],
)
def test_rejects_nonexact_write_resource(url):
    with pytest.raises(ValueError):
        validate_bitbucket_write_url(
            url, operation=Operation.CREATE_BRANCH, method="POST", expected_url=BRANCH
        )


@pytest.mark.parametrize("method", ["GET", "PUT", "PATCH", "DELETE", "post"])
def test_rejects_every_unapproved_mutation_method(method):
    with pytest.raises(ValueError):
        validate_bitbucket_write_url(
            BRANCH, operation=Operation.CREATE_BRANCH, method=method, expected_url=BRANCH
        )


def test_exact_owned_branch_endpoint_is_allowed():
    assert (
        validate_bitbucket_write_url(
            BRANCH, operation=Operation.CREATE_BRANCH, method="POST", expected_url=BRANCH
        )
        == BRANCH
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://bitbucket.org/acme/mobile/pull-requests/7",
        "https://evil.example/acme/mobile/pull-requests/7",
        "https://bitbucket.org.evil.example/acme/mobile/pull-requests/7",
        "https://user:secret@bitbucket.org/acme/mobile/pull-requests/7",
        "https://bitbucket.org:443/acme/mobile/pull-requests/7",
        "https://bitbucket.org/acme/other/pull-requests/7",
        "https://bitbucket.org/acme/mobile/pull-requests/8",
        "https://bitbucket.org/acme/mobile/pull-requests/7?redirect=evil",
        "https://bitbucket.org/acme/mobile/pull-requests/7#fragment",
        "https://bitbucket.org/acme/mobile/pull-requests/7/",
        "javascript:alert(1)",
        "/acme/mobile/pull-requests/7",
    ],
)
def test_public_pr_url_rejects_any_nonexact_navigation(url):
    with pytest.raises(ValueError):
        validate_pull_request_url(
            url, workspace="acme", repository_slug="mobile", pull_request_id=7
        )


def test_public_pr_url_is_exact_authorized_repository_and_integer_id():
    url = "https://bitbucket.org/acme/mobile/pull-requests/7"
    assert (
        validate_pull_request_url(
            url, workspace="acme", repository_slug="mobile", pull_request_id=7
        )
        == url
    )
    for invalid in [True, 0, -1, "7", 10**19]:
        with pytest.raises(ValueError):
            validate_pull_request_url(
                url, workspace="acme", repository_slug="mobile", pull_request_id=invalid
            )


@pytest.mark.parametrize("prefix", ["a" * 12, "a" * 39])
def test_pr_commit_resolution_is_a_separate_read_only_operation(prefix):
    url = "https://api.bitbucket.org/2.0/repositories/acme/mobile/commit/" + prefix
    assert (
        validate_bitbucket_write_url(
            url, operation=Operation.RESOLVE_PR_COMMIT, method="GET", expected_url=url
        )
        == url
    )
    for operation, method in [
        (Operation.READ_COMMIT, "GET"),
        (Operation.RESOLVE_PR_COMMIT, "POST"),
    ]:
        with pytest.raises(ValueError):
            validate_bitbucket_write_url(url, operation=operation, method=method, expected_url=url)


@pytest.mark.parametrize("prefix", ["a" * 11, "a" * 40, "main", "../main", "a" * 12 + "?q=x"])
def test_pr_commit_resolution_rejects_nonexact_prefix_resources(prefix):
    url = "https://api.bitbucket.org/2.0/repositories/acme/mobile/commit/" + prefix
    with pytest.raises(ValueError):
        validate_bitbucket_write_url(
            url, operation=Operation.RESOLVE_PR_COMMIT, method="GET", expected_url=url
        )
