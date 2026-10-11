# Public GitHub imports

In the product wizard, choose **Repositories → GitHub** and enter an
`owner/repository` pair or HTTPS URL. Select the branch and translation folder,
confirm the preview and base language, then import. Celery performs repository
reads in the background; no GitHub token is required.

Import, refresh, search, local editing and review are supported. Private GitHub
repositories and remote commits or pull requests are not supported. Use Bitbucket
Cloud for remote submission. VerboFlex never clones or executes imported code.

## Try different formats

Start with [VerboFlex Demo](https://github.com/smutti/verboflex-demo), which contains
synthetic Android XML, Qt TS, JSON and Apple strings files and a setup guide.
For additional public examples, inspect the current layouts of
[TranslateYou](https://github.com/you-apps/TranslateYou),
[Uptime Kuma](https://github.com/louislam/uptime-kuma),
[Flameshot](https://github.com/flameshot-org/flameshot) and
[Stats](https://github.com/exelban/stats). Their source and translations retain
their respective licenses. Always check the preview before importing.

## Limits and failures

Reads are pinned to commits and validate file size, Git hashes and paths.
Redirects, symlinks, submodules, truncated trees and unsupported structures fail
closed. A failed refresh preserves the previous active dataset.

Discovery is bounded to 500 candidate files, 1 MiB per file and 20 MiB combined;
GitHub trees are limited to 100,000 entries and 7 MiB. A mapping accepts up to
100,000 canonical values, 5,000 per file and 128 MiB of canonical output.
GitHub's unauthenticated API quota also applies; retry after the reported limit
resets instead of repeatedly starting imports.

[GitHub REST limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
· [Git trees](https://docs.github.com/en/rest/git/trees)
