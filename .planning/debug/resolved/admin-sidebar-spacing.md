---
status: resolved
trigger: "la parte di frontend ha qualche problema"
created: 2026-08-28
updated: 2026-08-28
---

# Debug Session: Admin sidebar spacing

## Symptoms

- expected: The `Administration` label and its `Products`, `Users`, and `Bitbucket` destinations form one compact navigation group below `Workspace overview` in the desktop sidebar.
- actual: On a tall desktop viewport, the Administration label and each destination are stretched vertically across almost the full sidebar height.
- errors: No runtime error is visible; this is a desktop layout regression.
- timeline: Visible in the current Phase 2 administrator frontend served locally on 2026-08-28.
- reproduction: Sign in as an administrator, open `/admin/products` at a desktop width and a tall viewport, then inspect the left sidebar.

## Current Focus

- hypothesis: Confirmed: a stretched CSS Grid nested in the desktop flex sidebar distributes unused block-axis space among implicit auto rows.
- test: Reproduce the exact AppShell class combination against the production stylesheet at a 1280x1262 viewport, inspect computed tracks, then add `content-start` only in the isolated reproduction.
- expecting: The current desktop `nav` stretches to the aside height and expands implicit rows; `content-start` keeps the same outer height while packing navigation tracks at the top.
- next_action: await authorization to add a failing geometry regression and apply the one-class fix
- reasoning_checkpoint:
- tdd_checkpoint: diagnose-only; no implementation authorized

## Evidence

- 2026-08-28: Screenshot shows the main Products content aligned normally while only the desktop sidebar's Administration rows occupy large, nearly even vertical bands.
- 2026-08-28: `AppShell.tsx` renders the desktop aside as `lg:flex` with a viewport-derived minimum height and renders its direct `nav` child as `grid w-full gap-6` without a block-axis content alignment rule.
- 2026-08-28: Browser reproduction against the production stylesheet measured the aside at 1197 px and the stretched nav at 1169 px. Its implicit rows became 532 px and 616 px; the nested Administration grid then produced four equal 148.75 px rows.
- 2026-08-28: The isolated addition of `content-start` to the shared nav changed computed `align-content` to `flex-start`; tracks compacted to 21 px and 105 px, with the four Administration rows at 21 px each.
- 2026-08-28: Existing AppShell tests verify labels, routes, visibility, responsive class names, overflow containment, and `aria-current`, but never assert rendered vertical geometry. JSDOM therefore let the CSS-only regression pass.
- 2026-08-28: The grid navigation entered in commit `ba9c7e9`; the final desktop `lg:flex`/full-height combination entered during Plan 02-16 and exposed the stretching interaction.

## Eliminated

- hypothesis: Product data, authentication state, or the Products empty state causes the spacing.
  evidence: The defect reproduces with static navigation markup and the production stylesheet, without API calls or application state.
- hypothesis: Each destination has an explicit margin, height, or `flex-1` utility.
  evidence: Destination buttons have only their normal minimum height; the computed 148.75 px tracks originate from grid track stretching.
- hypothesis: The main Products page grid stretches the sidebar links.
  evidence: The aside/nav standalone reproduction yields the same spacing and the main content geometry remains normal in the supplied screenshot.

## Resolution

- root_cause: The desktop aside is a tall row-direction flex container. Its direct navigation child is cross-axis stretched to the full aside height, and that child is also a CSS Grid with implicit auto rows and default `align-content: normal`. The free height is therefore added to the nav rows; the stretched Administration grid repeats the same behavior for its heading and three links.
- fix: Not applied in diagnose-only mode. The minimal verified correction is to add Tailwind `content-start` to the shared `WorkspaceNavigation` nav so its grid tracks remain compact at the top while desktop/mobile markup stays shared.
- verification: Production-CSS browser reproduction matched the screenshot geometry; the isolated one-class candidate compacted all tracks without changing markup, routing, or responsive visibility.
- files_changed: none in product code; diagnosis artifacts only
