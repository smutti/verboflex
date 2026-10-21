"""Build only the explicit public-site allowlist; Python standard library only."""

from __future__ import annotations

import argparse
import shutil
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

from content import COPY, SCREENSHOTS

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "dist"
C = COPY["en"]


def mark() -> str:
    return '<span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span>'


def arrow() -> str:
    return '<span aria-hidden="true">↗</span>'


def document(body: str, *, guide: bool, base_url: str) -> str:
    title = "User guide — VerboFlex" if guide else C["title"]
    description = C["guide_description"] if guide else C["description"]
    urls = [
        "index.html#product",
        "index.html#compose-screenshots",
        "index.html#workflow",
        "guide.html",
    ]
    nav = "".join(
        f'<a href="{url}"{chr(32) + 'aria-current="page"' if guide and i == 3 else ""}>{label}</a>'
        for i, (url, label) in enumerate(zip(urls, C["nav"]))
    )
    canonical = base_url + ("guide.html" if guide else "")
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>{escape(title)}</title>
  <meta name="description" content="{escape(description, quote=True)}">
  <link rel="canonical" href="{escape(canonical, quote=True)}">
  <meta property="og:type" content="website">
  <meta property="og:title" content="{escape(title, quote=True)}">
  <meta property="og:description" content="{escape(description, quote=True)}">
  <meta property="og:url" content="{escape(canonical, quote=True)}">
  <meta property="og:image" content="{escape(base_url, quote=True)}assets/social.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="VerboFlex. The right words. In every product.">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="theme-color" content="#133e35">
  <link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="assets/site.css">
  <script src="assets/site.js" defer></script>
</head>
<body{' class="guide-page"' if guide else ""}>
  <a class="skip-link" href="#main">{C["skip"]}</a>
  <header class="site-header">
    <div class="container header-inner">
      <a class="brand" href="index.html" aria-label="VerboFlex home">{mark()}VerboFlex<span class="brand-dot">.</span></a>
      <button class="menu-toggle" type="button" aria-expanded="false" aria-controls="site-nav" hidden>{C["menu"]} <span aria-hidden="true">☰</span></button>
      <nav id="site-nav" aria-label="Main navigation">{nav}</nav>
      <a class="header-cta" href="https://github.com/smutti/verboflex">View on GitHub {arrow()}</a>
    </div>
  </header>
  <main id="main">{body}</main>
  <footer class="site-footer">
    <div class="container footer-top"><div><a class="brand" href="index.html">{mark()}VerboFlex<span class="brand-dot">.</span></a><p>{C["footer"]}</p></div><nav aria-label="Footer"><a href="https://github.com/smutti/verboflex">GitHub</a><a href="guide.html">User guide</a><a href="guide.html#mcp">MCP setup</a><a href="guide.html#operations">For administrators</a></nav></div>
    <div class="container footer-bottom"><span>VerboFlex · <a href="https://github.com/smutti/verboflex/blob/main/LICENSE">Apache 2.0</a></span><span>{C["footer_note"]}</span></div>
  </footer>
</body>
</html>
'''


def demo() -> str:
    tabs = "".join(
        f'<button type="button" data-view="{view}" aria-pressed="{str(view == "translations").lower()}" aria-controls="demo-{view}"><span class="demo-tab-icon" aria-hidden="true">{icon}</span>{name}</button>'
        for view, name, icon in zip(
            ["overview", "translations", "review"], C["demo_tabs"], ["◫", "文", "✓"]
        )
    )
    metrics = "".join(
        f"<div><strong>{number}</strong><span>{label}</span></div>"
        for number, label in zip(["1,200", "2,940", "660"], C["stats"])
    )
    bars = "".join(
        f'<div class="coverage-row"><div><strong>{name}</strong><span>{missing} missing · {percent}%</span></div><div class="coverage-track"><span style="width:{percent}%"></span></div></div>'
        for name, missing, percent in [
            ("Deutsch", "360", 70),
            ("Italiano", "240", 80),
            ("Français", "60", 95),
        ]
    )
    return f"""
<section id="demo" class="container demo-section" aria-label="Interactive product demonstration">
  <div class="demo-caption"><span><span class="live-dot" aria-hidden="true"></span>{C["demo_label"]}</span><span>{C["demo_note"]}</span></div>
  <div class="demo-shell">
    <aside class="demo-sidebar"><div class="demo-brand">{mark()}<span>VerboFlex</span></div><div class="demo-project"><span class="project-icon">H</span><span>Horizon<small>{C["demo_project"]}</small></span></div><div class="demo-navigation" role="group" aria-label="Demo views">{tabs}</div><div class="demo-user"><span class="avatar">JL</span><span>Jamie Lee<small>Reviewer · demo</small></span></div></aside>
    <div class="demo-main">
      <div class="demo-toolbar"><span>Horizon <span aria-hidden="true">/</span> <strong data-current-view>Translations</strong></span><button type="button" class="reset-button" data-reset>{C["demo_reset"]} <span aria-hidden="true">↺</span></button></div>
      <div id="demo-translations" class="demo-panel">
        <div class="demo-panel-heading"><h2>{C["demo_title"]}</h2><p>{C["demo_description"]}</p></div>
        <div class="translation-grid">
          <div class="key-cell"><span class="micro-label">{C["key"]}</span><strong>checkout.confirm</strong><span class="file-label">locales / checkout.json</span><span class="key-limit">↔ 24 characters</span></div>
          <div class="language-rows">
            <div class="language-row"><div class="language-label"><strong>English</strong><span>en · {C["source"]}</span></div><div class="read-value">Confirm order <span class="source-badge">{C["source"]}</span></div></div>
            <div class="language-row editing"><div class="language-label"><strong>Italiano</strong><span>it</span></div><div class="edit-cell"><label class="sr-only" for="demo-translation">{C["edit"]}</label><div class="input-wrap"><textarea id="demo-translation" rows="1" readonly aria-describedby="demo-counter demo-input-hint" spellcheck="false" lang="it">Conferma</textarea><span aria-hidden="true">✎</span></div><div class="edit-meta"><span id="demo-counter">8 / 24 characters</span><span class="state-badge" data-draft-status hidden>{C["draft"]}</span></div><div class="edit-actions"><button type="button" class="button button-small" data-save>{C["save"]}</button><span id="demo-input-hint">{C["demo_hint"]}</span></div></div></div>
            <div class="language-row"><div class="language-label"><strong>Deutsch</strong><span>de</span></div><div class="read-value missing-value">{C["empty"]} <span aria-hidden="true">—</span></div></div>
          </div>
        </div>
      </div>
      <div id="demo-overview" class="demo-panel" hidden><div class="demo-panel-heading"><h2>{C["overview_title"]}</h2><p>{C["overview_description"]}</p></div><div class="demo-metrics">{metrics}</div><div class="coverage"><h3>{C["coverage"]}</h3>{bars}</div><p class="demo-footnote">{C["coverage_note"]}</p></div>
      <div id="demo-review" class="demo-panel" hidden><div class="demo-panel-heading"><h2>{C["review_title"]}</h2><p>{C["review_description"]}</p></div><div class="review-card"><div class="review-card-heading"><code>checkout.confirm</code><span>Italiano</span></div><div class="review-diff"><div><span>{C["before"]}</span><p>Conferma</p></div><div><span>{C["after"]}</span><p data-proposal>{C["review_empty"]}</p></div></div><div class="review-actions"><button type="button" class="button button-small" data-approve disabled>{C["approve"]}</button><span data-review-state></span></div></div><p class="demo-footnote">{C["review_note"]}</p></div>
      <p class="demo-status" role="status" aria-live="polite" aria-atomic="true"></p>
    </div>
  </div>
  <p class="callout no-js-note">This is an illustrative preview. Enable JavaScript to try editing and review, or <a href="guide.html">read the guide</a>.</p>
</section>"""


def screenshot_figure(shot: dict, *, guide: bool = False) -> str:
    path = f"assets/screenshots/{shot['name']}.jpg"
    caption = f"<strong>{escape(shot['title'])}</strong><p>{escape(shot['text'])}</p>"
    if not guide:
        caption += f'<a class="text-link" href="guide.html#{shot["guide"]}">How to use it {arrow()}</a>'
    return f'''<figure class="product-shot{" guide-shot" if guide else ""}">
      <a class="shot-link" href="{path}" aria-label="Open full-size screenshot: {escape(shot["title"], quote=True)}">
        <img src="{path}" width="1280" height="{shot["height"]}" loading="lazy" decoding="async" alt="{escape(shot["alt"], quote=True)}">
        <span>View full size {arrow()}</span>
      </a><figcaption>{caption}</figcaption></figure>'''


def gallery() -> str:
    shots = "".join(screenshot_figure(shot) for shot in SCREENSHOTS)
    return f"""<section id="screenshots" class="section container screenshot-section">
      <div class="section-heading"><p class="eyebrow">INSIDE THE APP</p>
        <h2>A workspace for<br>the whole translation.</h2>
        <p>Actual VerboFlex screens with Northstar demo data. Captured October 2026.</p>
      </div><div class="screenshot-grid">{shots}</div></section>"""


def compose_showcase() -> str:
    code = escape("""@Preview
@Composable
fun CheckoutPreview() {
    CheckoutScreen(
        confirmLabel = stringResource(
            R.string.confirm_order
        )
    )
}""")
    return f"""
<section id="compose-screenshots" class="section container compose-section" aria-labelledby="compose-title">
  <div class="compose-heading">
    <div><p class="eyebrow">NEW · SCREENSHOTS FROM COMPOSE CODE</p><h2 id="compose-title">See your translation.<br><em>In the screen it belongs to.</em></h2></div>
    <div><p>Generate screenshots directly from your Android Compose previews, with your saved translation applied. Review wording, wrapping and spacing beside the text before you approve.</p><a class="text-link" href="guide.html#compose-screenshots">Explore the screenshot workflow {arrow()}</a></div>
  </div>
  <figure class="compose-illustration">
    <div class="compose-panels">
      <div class="compose-input">
        <div class="compose-panel-label"><span>01 / APPLICATION CODE</span><span>Checkout.kt</span></div>
        <pre><code>{code}</code></pre>
        <div class="compose-proposal"><span>02 / SAVED TRANSLATION · ITALIAN</span><strong lang="it">Conferma ordine</strong><p>confirm_order <span aria-hidden="true">·</span> 15 / 24 characters</p></div>
      </div>
      <div class="compose-output">
        <div class="compose-panel-label"><span>03 / SCREEN CONTEXT</span><span class="compose-tag">Compose preview</span></div>
        <div class="compose-phone" lang="it">
          <div class="compose-phone-top"><span aria-hidden="true">←</span><strong>Il tuo ordine</strong><span aria-hidden="true">⋯</span></div>
          <div class="compose-phone-body"><span class="compose-shop">NORTHSTAR / DEMO</span><h3>Pronto per partire?</h3><p>Controlla il tuo ordine prima di confermare.</p><div class="compose-order"><span>Pass giornaliero<small>1 persona</small></span><strong>€ 12,00</strong></div><div class="compose-total"><span>Totale</span><strong>€ 12,00</strong></div><div class="compose-highlight"><span class="compose-screen-button">Conferma ordine</span><span class="compose-highlight-note">confirm_order</span></div></div>
        </div>
      </div>
    </div>
    <figcaption>Illustrated workflow with sample data. In VerboFlex, the configured Compose runner generates the actual screenshot from your application code.</figcaption>
  </figure>
  <div class="compose-benefits">
    <div><h3>Save. Generate. Review.</h3><p>Save your wording, choose a registered preview and request a screenshot. Generation runs in the background.</p></div>
    <div><h3>Text left. Screenshot right.</h3><p>Keep the source, proposal and review actions together. Open the screenshot at full size when you need a closer look.</p></div>
    <div><h3>Know when to regenerate.</h3><p>Older captures and unsaved changes are flagged. Generate again after saving to inspect the latest proposal.</p></div>
  </div>
  <p class="compose-requirement">For configured Android Compose projects. Your team registers a callable preview and prepares a capture runner. <a href="guide.html#compose-setup">See developer setup</a>.</p>
</section>"""


def landing() -> str:
    features = "".join(
        f'<article><span class="feature-number">{n}</span><h3>{title}</h3><p>{text}</p></article>'
        for n, title, text in C["features"]
    )
    steps = "".join(
        f'<li><span class="step-number">0{i + 1}</span><h3>{title}</h3><p>{text}</p></li>'
        for i, (title, text) in enumerate(C["steps"])
    )
    roles = "".join(
        f'<div><span class="role-mark" aria-hidden="true">{icon}</span><h3>{title}</h3><p>{text}</p></div>'
        for icon, (title, text) in zip(["✎", "✓", "⚙", "◎"], C["roles"])
    )
    faqs = "".join(
        f"<details><summary>{title}</summary><p>{text}</p></details>"
        for title, text in C["faqs"]
    )
    return f"""
<section class="hero container">
  <div class="hero-copy"><p class="eyebrow"><span class="live-dot" aria-hidden="true"></span>{C["eyebrow"]}</p><h1>{C["headline"]}</h1><p class="hero-intro">{C["intro"]}</p><div class="hero-actions"><a class="button" href="#demo">{C["primary"]} <span aria-hidden="true">↓</span></a><a class="text-link" href="#compose-screenshots">See Compose screenshots {arrow()}</a></div><p class="hero-note">{C["hero_note"]}</p></div>
  <div class="word-orbit" aria-hidden="true"><div class="orbit-ring"></div><div class="orbit-center">Aa<span>One shared meaning.</span></div><span class="word word-one">Hello<span>English</span></span><span class="word word-two">Ciao<span>Italiano</span></span><span class="word word-three">こんにちは<span>日本語</span></span><span class="word word-four">Bonjour<span>Français</span></span><span class="orbit-spark">✳</span><span class="orbit-coordinate">Words that travel.</span></div>
</section>
{compose_showcase()}
{demo()}
<section id="product" class="section container"><div class="section-heading"><p class="eyebrow">{C["section_label"]}</p><h2>{C["features_title"]}</h2></div><div class="feature-grid">{features}</div></section>
{gallery()}
<section id="workflow" class="workflow-section"><div class="container"><div class="section-heading"><p class="eyebrow">{C["workflow_label"]}</p><h2>{C["workflow_title"]}</h2></div><ol class="workflow-grid">{steps}</ol><p class="workflow-note">{C["workflow_note"]}</p><a class="light-link" href="guide.html#connect">Follow the complete workflow {arrow()}</a></div></section>
<section id="integrations" class="section container"><div class="section-heading"><p class="eyebrow">{C["integrations_label"]}</p><h2>{C["integrations_title"]}</h2><p>{C["integrations_intro"]}</p></div><div class="provider-grid"><article class="provider-card"><div class="provider-top"><span class="provider-symbol" aria-hidden="true">⌘</span><span class="pill">{C["bitbucket_label"]}</span></div><h3>Bitbucket Cloud</h3><p>{C["bitbucket_text"]}</p><a class="text-link" href="guide.html#connect">Connect a repository {arrow()}</a></article><article class="provider-card"><div class="provider-top"><span class="provider-symbol" aria-hidden="true">⌥</span><span class="pill neutral">{C["github_label"]}</span></div><h3>GitHub</h3><p>{C["github_text"]}</p><a class="text-link" href="guide.html#connect">Explore the supported workflow {arrow()}</a></article></div><div class="format-strip"><h3>{C["formats"]}</h3><div><span>Android XML</span><span>Qt .ts</span><span>JSON</span><span>Apple .strings</span><span>{C["xliff"]}</span></div><p>{C["format_note"]}</p></div></section>
<section class="people-section"><div class="container"><p class="eyebrow">{C["people_label"]}</p><h2>{C["people_title"]}</h2><div class="roles-grid">{roles}</div></div></section>
<section class="section container mcp-section"><div><p class="eyebrow">{C["mcp_label"]}</p><h2>{C["mcp_title"]}</h2><p>{C["mcp_text"]}</p><a class="text-link" href="guide.html#mcp">{C["mcp_link"]} {arrow()}</a></div><div class="assistant-card"><div class="assistant-card-top"><span class="live-dot" aria-hidden="true"></span>VerboFlex MCP <span>OAuth</span></div><span class="micro-label">{C["mcp_prompt_label"]}</span><blockquote>{C["mcp_prompt"]}</blockquote><div class="assistant-scopes"><code>verboflex:read</code><span>Read access first. Write access by consent.</span></div></div></section>
<section class="section container faq-section"><div><p class="eyebrow">A FEW USEFUL ANSWERS</p><h2>{C["faq_title"]}</h2><a class="text-link" href="guide.html#help">More in the guide {arrow()}</a></div><div>{faqs}</div></section>
<section class="closing-section container"><div><h2>{C["closing"]}</h2><p>{C["closing_text"]}</p></div><a class="button" href="guide.html#start">{C["secondary"]} {arrow()}</a></section>"""


def guide_body() -> str:
    toc = "".join(
        f'<a href="#{anchor}">{title}</a>' for anchor, title in C["guide_sections"]
    )
    body = (ROOT / "guide.html").read_text()
    for shot in SCREENSHOTS:
        body = body.replace(
            f"<!-- screenshot: {shot['name']} -->",
            f'<details class="guide-screenshot"><summary>See it in the app</summary>{screenshot_figure(shot, guide=True)}</details>',
        )
    return f'''<div class="container guide-hero"><p class="eyebrow">{C["guide_label"]}</p><h1>{C["guide_title"]}</h1><p>{C["guide_description"]}</p></div><div class="container guide-layout"><aside class="guide-toc"><nav aria-label="{C["guide_toc"]}"><h2>{C["guide_toc"]}</h2>{toc}</nav></aside><article class="guide-content">{body}</article></div>'''


def build(base_url: str) -> None:
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
        or parsed.username
    ):
        raise ValueError(
            "--base-url must be a public HTTPS URL without credentials, query or fragment"
        )
    base_url = base_url.rstrip("/") + "/"
    if OUT.is_symlink():
        raise ValueError("site/dist must be a directory, not a symlink")
    OUT.mkdir(exist_ok=True)
    # Remove only our dedicated generated directory. Never copy repository docs or secrets.
    for child in OUT.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    (OUT / "assets").mkdir()
    for name in ("site.css", "site.js", "favicon.svg", "social.png"):
        shutil.copyfile(ROOT / "assets" / name, OUT / "assets" / name)
    (OUT / "assets" / "screenshots").mkdir()
    for shot in SCREENSHOTS:
        name = shot["name"] + ".jpg"
        shutil.copyfile(
            ROOT / "assets" / "screenshots" / name,
            OUT / "assets" / "screenshots" / name,
        )
    (OUT / "index.html").write_text(document(landing(), guide=False, base_url=base_url))
    (OUT / "guide.html").write_text(
        document(guide_body(), guide=True, base_url=base_url)
    )
    (OUT / ".nojekyll").touch()
    (OUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {base_url}sitemap.xml\n"
    )
    (OUT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{escape(base_url)}</loc></url><url><loc>{escape(base_url)}guide.html</loc></url></urlset>\n'
    )
    print(f"Built {OUT}: English product page, guide and local assets.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://smutti.github.io/verboflex/")
    build(parser.parse_args().base_url)
