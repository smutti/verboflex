"""Provider read pools, separate from Bitbucket's write adapter and credentials."""

from verboflex.core.config import Settings
from verboflex.integrations.bitbucket.client import BitbucketHttpAdapter, BitbucketProviderReadError
from verboflex.integrations.github.client import GitHubHttpAdapter
from verboflex.services.bitbucket_oauth import BitbucketOAuthService, BitbucketOAuthTokenExchange


class RepositoryReadAdapters:
    def __init__(self, bitbucket: BitbucketHttpAdapter | None, github: GitHubHttpAdapter) -> None:
        self.bitbucket = bitbucket
        self.github = github

    def for_provider(self, provider: str) -> BitbucketHttpAdapter | GitHubHttpAdapter:
        if provider == "github":
            return self.github
        if provider == "bitbucket" and self.bitbucket is not None:
            return self.bitbucket
        raise BitbucketProviderReadError(kind="disconnected")

    async def aclose(self) -> None:
        await self.github.aclose()
        if self.bitbucket is not None:
            await self.bitbucket.aclose()


def create_repository_read_adapters(settings: Settings) -> RepositoryReadAdapters:
    bitbucket = None
    try:
        oauth = BitbucketOAuthService(
            settings=settings, token_exchange=BitbucketOAuthTokenExchange()
        )
        bitbucket = BitbucketHttpAdapter(settings=settings, credential_leases=oauth)
    except ValueError:
        pass
    return RepositoryReadAdapters(bitbucket, GitHubHttpAdapter())
