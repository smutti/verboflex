# VerboFlex

[![Application checks](https://github.com/smutti/verboflex/actions/workflows/application-check.yml/badge.svg)](https://github.com/smutti/verboflex/actions/workflows/application-check.yml) [![Website checks](https://github.com/smutti/verboflex/actions/workflows/site-check.yml/badge.svg)](https://github.com/smutti/verboflex/actions/workflows/site-check.yml)

**Self-hosted localization review, connected to your repositories.**

[Website and demo](https://smutti.github.io/verboflex/) · [User guide](https://smutti.github.io/verboflex/guide.html) · [Deploy a demo](docs/demo-deployment.md) · [Apache 2.0](LICENSE)

VerboFlex gives translators, reviewers and product teams a shared workspace over localization files. Compare languages on the same key, propose edits, check character limits, discuss wording and send approved changes through a Bitbucket Cloud pull request.

## Explore the product

The English product website and user guide live in [`site/`](site/README.md). They include an interactive demonstration with sample data, repository and format support, user workflows, troubleshooting, and OAuth setup for Codex and Claude Code.

Preview locally with Python 3.12 or later:

```sh
python3 site/build.py
python3 site/check.py
python3 -m http.server 4174 --bind 127.0.0.1 --directory site/dist
```

Open [the product website](http://127.0.0.1:4174) or [the user guide](http://127.0.0.1:4174/guide.html). The preview is separate from the VerboFlex application and does not access its database.

See the [current application screenshots](https://smutti.github.io/verboflex/#screenshots). Site changes on `main` are checked and published automatically through GitHub Pages. See [site maintenance and publication](site/README.md).

For a live portal walkthrough, import [VerboFlex Demo](https://github.com/smutti/verboflex-demo): four synthetic products, four languages and 400 localization values covering missing translations, native plurals, reuse, glossary and character limits. It includes an [installation recipe](https://github.com/smutti/verboflex-demo/blob/main/docs/setup.md) and a [10-minute presenter guide](https://github.com/smutti/verboflex-demo/blob/main/docs/presenter-guide.md). GitHub imports support local review; remote submission still requires Bitbucket Cloud.

## What you can do

- See product coverage, missing translations, notifications and recent activity.
- Search and filter strings, compare multiple languages, and edit eligible values inline.
- Fill missing translations, add keys in existing files and edit native Android/Qt plural forms.
- Reuse exact or similar translations from the same product and consult glossary hints.
- Save drafts, discuss changes with comments and mentions, and approve or reject proposals.
- Generate screenshots from configured Android Compose previews to review saved translations in their screen context.
- Refresh from repositories and reconcile proposals when their source changes.
- Prepare approved changes for Bitbucket Cloud pull requests.
- Connect assistants through the HTTP MCP server with OAuth, using the same user roles.

| Source          | Import / refresh | Local editing / review | Remote submission              |
| --------------- | ---------------- | ---------------------- | ------------------------------ |
| Bitbucket Cloud | Yes              | Eligible formats       | Branch / commit / pull request |
| Public GitHub   | Yes              | Eligible formats       | Not yet supported              |

Private GitHub repositories are not supported. Android XML, Qt `.ts`, JSON and Apple `.strings` support eligible edits; XLIFF supports import and reading. File structure and source provenance determine whether an individual value is editable.

## Screenshots from Compose code

Generate a screenshot from a registered Android Compose preview with the saved
translation applied. Review the source, proposal and character limit on the left,
with the screenshot on the right. Older images are flagged after edits so reviewers
know when to save and generate again.

Your team prepares a callable preview and capture runner; generation runs on request
in the background. The image shows the preview’s fixture state, not a live device.
See the [visual walkthrough](https://smutti.github.io/verboflex/#compose-screenshots),
[reviewer guide](https://smutti.github.io/verboflex/guide.html#compose-screenshots)
and [developer setup](docs/code-keys-compose.md).

## Application and operations

The application is a React/Vite frontend and FastAPI backend with PostgreSQL, Redis and Celery. GitHub Pages hosts documentation only; it cannot host the backend or workers.

| Area                            | Entry point                                                                                      |
| ------------------------------- | ------------------------------------------------------------------------------------------------ |
| Frontend                        | [`frontend/`](frontend/)                                                                         |
| Backend, workers and migrations | [`backend/`](backend/)                                                                           |
| Container services              | [`docker-compose.yml`](docker-compose.yml), [`docker-compose.prod.yml`](docker-compose.prod.yml) |
| Configuration example           | [`.env.example`](.env.example)                                                                   |
| MCP OAuth and local stdio setup | [`mcp-server/README.md`](mcp-server/README.md)                                                   |
| Backup and restore              | [`docs/backup-restore.md`](docs/backup-restore.md)                                               |
| Database maintenance            | [`docs/database-maintenance.md`](docs/database-maintenance.md)                                   |
| Public GitHub imports           | [`docs/github-imports.md`](docs/github-imports.md)                                               |
| Kotlin/Java keys and Compose screenshots | [`docs/code-keys-compose.md`](docs/code-keys-compose.md) |

## Run your own workspace

Follow the [Docker + HTTPS deployment recipe](docs/demo-deployment.md) to generate
private configuration, migrate an empty database, create an administrator and load
synthetic sample products. Use individual accounts for live trials. The current
portal shares products between users; an anonymous, isolated editing sandbox is
not implemented.

For development, use the [application check guide](docs/application-ci.md).
[Load-test tooling and measured limits](docs/load-testing.md) are available;
benchmarks do not establish support for tens of millions of strings.

## Contribute and license

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
VerboFlex is licensed under the [Apache License, Version 2.0](LICENSE).
Third-party dependencies and imported localization content retain their own licenses.
Do not commit deployment environment files, credentials or database backups.
