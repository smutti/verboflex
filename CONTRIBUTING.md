# Contributing to VerboFlex

Open an issue describing the user problem and a small reproducible example. Use
synthetic strings; do not include private repositories, credentials or database dumps.
Discuss substantial changes before opening a large pull request.

The [CODEOWNERS file](.github/CODEOWNERS) requests review from `@smutti` for all
paths on ready pull requests opened by other authors. This takes effect once the
file is on the pull request's base branch. Review assignment and mandatory
approval are separate settings; CODEOWNERS does not enable mandatory approval.
GitHub does not allow authors to approve their own pull requests. For self-authored
changes, inspect the diff and merge manually after the required checks pass.

Use Python 3.14.7+, Node 24, uv and Docker. The [application check guide](docs/application-ci.md)
lists setup, unit/integration tests, contract generation and the built-stack smoke.
Run the checks relevant to your change and explain their results in the pull request.

Keep frontend and backend separate. Run repository work in Celery, enforce permissions
in the API, use Alembic for schema changes and preserve localization file structure.
Parser and serializer changes need fixtures covering round trips and unsupported input.
Keep product copy and documentation in English and update the guide when behavior changes.

Contributions are provided under the [Apache License 2.0](LICENSE). Preserve third-party
notices. See [SECURITY.md](SECURITY.md) for vulnerability reporting.
