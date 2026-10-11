# Product website

The English-only VerboFlex website explains the product and its workflows. It contains a landing page, a practical user guide, a synthetic interactive demo, a favicon and a social sharing card. It has no application connection, analytics, remote fonts or runtime dependencies.

## Preview and check

Use Python 3.12+ from the repository root:

```sh
python3 site/build.py
python3 site/check.py
python3 -m http.server 4174 --bind 127.0.0.1 --directory site/dist
```

Open <http://127.0.0.1:4174>. The build publishes exactly nine allowlisted files into ignored `site/dist/`; it does not copy internal documentation, source code, environment files or application data.

The browser check reuses the existing frontend Playwright installation. If necessary, install the frontend's locked development dependencies and its Chromium browser first:

```sh
npm --prefix frontend ci
cd frontend
npx playwright install chromium
cd ..
node site/tests/browser.mjs
# Optional second engine, if its Playwright browser is installed:
SITE_BROWSER=webkit node site/tests/browser.mjs
```

It serves an isolated copy under `/verboflex/` and checks editing, approval, over-limit drafts, safe text rendering, grapheme counting, five viewport widths, guide anchors, mobile keyboard navigation, reduced motion and content with JavaScript disabled. It makes no requests to the running application. Port 4175 is the default; set `SITE_TEST_PORT` to change it.

## Edit the content

| File                | Purpose                                                              |
| ------------------- | -------------------------------------------------------------------- |
| `content.py`        | Landing-page copy and guide navigation                               |
| `guide.html`        | Practical user guide; body sections only                             |
| `build.py`          | Shared layout, product demonstration and explicit artifact allowlist |
| `assets/site.css`   | Responsive styling, reduced motion and focus states                  |
| `assets/site.js`    | In-memory demo and optional navigation behavior                      |
| `social.html`       | Editable source for the social sharing card                          |
| `assets/social.png` | Committed 1200 × 630 sharing card                                    |
| `check.py`          | Artifact, links, anchors and metadata validation                     |
| `SOURCE-MAP.md`     | Capability evidence for maintainers; not published                   |

To regenerate the card after changing its source:

```sh
node site/tests/render-social.mjs
python3 site/build.py
python3 site/check.py
```

Use only sample names and invented strings in demonstrations. Label them as illustrative; the demo is not a pixel-for-pixel screenshot of the application. Keep claims aligned with `SOURCE-MAP.md`, including GitHub and XLIFF limitations. Do not imply a hosted signup, automatic machine translation or tested large-scale throughput.

## Publish on GitHub Pages

The project site is designed for `https://smutti.github.io/verboflex/`.
Publish the reviewed source from `main` in the existing `smutti/verboflex` repository.

1. In **Settings → Pages → Build and deployment**, choose **GitHub Actions**.
2. Review the `site/dist/` artifact and configure the `github-pages` environment.
3. In **Actions → Publish product website**, run the workflow on `main`.
4. Open the returned deployment URL; verify the guide, interactive demo and social card.

The workflow is manual: pushing application code does not deploy the site or the
live portal. It validates and uploads only `site/dist/`. Action versions are pinned,
and write permissions are confined to the deployment job. **Check product website**
builds and validates relevant pushes and pull requests without publishing.

The Pages action supplies the canonical URL during deployment, including a configured custom domain. For a local build with another destination:

```sh
python3 site/build.py --base-url https://docs.example.org/verboflex/
```

All browser assets and navigation links are relative, so the site works under a repository path or a custom domain. Canonical URLs, the sitemap and social metadata use `--base-url`. The generated directory contains no server-side code.

References: [GitHub Pages availability and behavior](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages), [custom Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## Publication boundaries

- This website is documentation, not the VerboFlex application. It has no login or live backend.
- The demo saves only to page memory; reloading or resetting clears it. Overview statistics are a separate fixed sample, not live totals for the demo row.
- Source is licensed under Apache 2.0. The user guide links to the repository and its deployment runbooks.
- No application screenshots or private customer/project names are published. `SOURCE-MAP.md`, this README, tests and HTML card source are also excluded from the artifact.
- To update or roll back the site, review the appropriate site commit on `main` and run the manual publication workflow again. No automatic application deployment is involved.
