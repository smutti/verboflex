# Phase 04 — UI Review

**Audited:** 2026-09-06
**Baseline:** approved `04-UI-SPEC.md`, `04-CONTEXT.md`, Phase 04 plan/summary context
**Screenshots:** captured from current source with fixture-backed Chromium; admin preview/import findings use code and existing test evidence
**Current targeted recheck: 24/24 — all 12 findings closed**
**Historical initial audit: 14/24 — retained below without erasing its findings**

## Targeted correction recheck — 2026-09-06

Reviewed correction GREEN `585422878f96602d944e3b03d3c399761ada2706` following RED `d4f8dc4`. At the browser recheck, the inspected frontend production files had no diff from that GREEN commit. Independent recheck used an owned current-source Vite server on 127.0.0.1:4175 and fixture-backed Chromium at 320/375/768/1024/1440px. The server was stopped afterward. This is a bounded adjudication of the original 12 findings, not a new broad audit.

**Final residual closure:** independently inspected `7d3f9d3f9e5e981b3d6e2fc3ce2ea72f979a4851` following RED `d537db1`. Its entire production change is the single `font-medium` → `font-semibold` class replacement on the `Base language required` paragraph at `ProductPreviewPage.tsx:497`; current source contains the corrected class. T-01 is now closed on source evidence for this administrator-only residual. The prior 23/24 intermediate score became 24/24 solely by restoring Typography from 3 to 4. The three targeted tests reported by the executor were not independently rerun, and the already verified nine browser checks were not repeated for this one-class admin change. No new administrator visual or native-zoom claim is made.

The targeted `--grep UI4` suite passed **9/9** (eight browser tests plus the inventory check), and the original independent measurement driver was rerun against corrected source. New screenshots are in `.planning/ui-reviews/04-20260906-recheck/`; initial audit images were preserved. Screenshots from the implementation correction also exist separately in `.planning/ui-reviews/04-20260906-correction/`. The screenshot ignore gate was checked before capture. Native browser 200% zoom and current-build administrator screenshots remain **unverified**. The executor's reported full 21-browser/307-component pass is not presented as an independently rerun result here.

Rechecked source fingerprint: `7c37a8ff227dd3847c8b2ab3d4ae459e366bb05a7f086359f024c8b2937954ab`, using the initial audit's path/content/NUL recipe, now 36 production files because `translationFilterLabels.ts` was added. Observed repository HEAD was `06d738f993fd69162f2ed9585e5d31e6a7ada274`; unrelated delivery work does not change the exact correction revision above.

| Pillar | Initial | Current | Evidence supporting current score |
|---|---:|---:|---|
| Copywriting | 3/4 | 4/4 | Approved display labels now appear in the filtered-empty criteria; CW-01 browser assertion passes. |
| Visuals | 3/4 | 4/4 | Current navigation is visibly distinguished in desktop and mobile; the complete mutation outcome wraps without clipping. |
| Color | 2/4 | 4/4 | Focused option contrast is 16.96:1; skeletons are neutral and the inspected Secondary/warning surfaces use the declared tokens. |
| Typography | 2/4 | 4/4 | Measured translation primitives match their declared roles; the final source-only correction gives the admin base-language blocker the approved 600 weight. |
| Spacing | 2/4 | 4/4 | Shell gutters measure 24/32px, dialog padding/gap 24/16px, and the measured field/retry targets are 44px. |
| Experience Design | 2/4 | 4/4 | Persistent detail heading, explicit retry focus, retained query and disabled decorative reduced-motion animations pass. |

These scores reflect the original audit plus this targeted correction evidence. A 4 means no remaining finding in that reviewed scope; it does not certify untested administrator rendering, native zoom or deployment behavior.

| Finding | Disposition | Corrective evidence |
|---|---|---|
| CW-01 | CLOSED | `translationFilterLabels.ts:1`, consumed in `TranslationSearchPage.tsx:246` and `TranslationFilters.tsx:58`; browser shows `Approved`, `No max length`, `Active and deleted` instead of transport enums. |
| V-01 | CLOSED | `AppShell.tsx:132` applies a current background, 600 weight and accent border; desktop screenshot and mobile Sheet assertions distinguish the current link. |
| V-02 | CLOSED | `alert.tsx:42` removes the one-line clamp. At 320px, the refresh-error title has clientHeight=scrollHeight=63px and clamp `none`; all title text is visible. |
| C-01 | CLOSED | `select.tsx:113` uses neutral focus colors. Measured `#111827` on `#F8FAFC` gives **16.96:1**, with 14px text. Outline/ghost hover source uses the same corrected neutral treatment. |
| C-02 | CLOSED | `skeleton.tsx:8` uses `bg-border`; all 30 loading blocks measure `#E5E7EB`, with no accent-colored skeleton surface. |
| C-03 | CLOSED | Search/filter regions and dialogs are white Secondary surfaces; `TranslationDetailPage.tsx:321` uses the warning token and its color measures `#B45309`. |
| T-01 | CLOSED | Search/filter labels measure 12px/600/15.6px line height; controls and descriptions 14px/400; dialog title 20px/600. Final commit `7d3f9d3f9e5e981b3d6e2fc3ce2ea72f979a4851` changes the sole remaining Phase 04 base-language blocker to `className="font-semibold text-warning"` at `ProductPreviewPage.tsx:497`. This final admin residual is verified by exact production diff/current source, not an administrator screenshot. |
| S-01 | CLOSED | Main gutters measure 24px below 768px and 32px at/above it; constraint dialog padding is 24px and gap 16px. |
| S-02 | CLOSED | Numeric field and Retry search each measure 44px at 320px. Base-language SelectItem now explicitly uses `min-h-[44px] min-w-[44px]` at `ProductPreviewPage.tsx:485`; that admin portion is source-verified. |
| E-01 | CLOSED | Loading/error retain exactly one h1. Initial error does not steal focus; explicit failed retry focuses the owning Alert. Driver prints `h1:1`, then retry focus `DIV`, corroborated by a focus-specific browser assertion. |
| E-02 | CLOSED | Query input exists through held options and 503; the browser test retains `retained query` through product reauthorization. Retry remains present at 44px. |
| E-03 | CLOSED | Reduced-motion skeleton and search Select animation duration is 0s/name `none`; the constraint dialog's animation name is `none`. Matching overrides are present on Dialog/AlertDialog overlays and content. |

Reproduction for these targeted checks, with the same already installed dependencies and a Vite server on 4175:

```sh
UI_AUDIT_DIR=/Users/smutti/Documents/personal/verboflex/.planning/ui-reviews/04-20260906-recheck node /tmp/verboflex-ui-audit.mjs
cd /Users/smutti/Documents/personal/verboflex/frontend
PLAYWRIGHT_BASE_URL=http://127.0.0.1:4175 PLAYWRIGHT_OUTPUT_DIR=/tmp/verboflex-ui-recheck-e2e ./node_modules/.bin/playwright test e2e/translations.spec.ts --grep UI4
```

**Current recommendation count:** zero remaining priority findings; zero remaining minor recommendations among the original 12 findings. The initial audit and its historical recommendation count follow unchanged for traceability.

## Historical initial audit — 14/24

## Evidence boundary

The audited source was served by a new, isolated Vite process at `http://127.0.0.1:4175`. Ports 3000 and 5173 were unavailable; existing localhost:8080 returned 200 but was deliberately excluded because its deployed revision was not established. All API requests in the audit browser were intercepted using the existing translation E2E fixtures. No provider calls, real credentials, package installs, production edits, or commits were performed.

Starting HEAD: `8ee6d09f73c01c003e09627512ddbc789b83bb91`. The source fingerprint for the sorted production `.ts/.tsx` files in `frontend/src/features/translations/` and `frontend/src/components/ui/`, plus `index.css`, `router.tsx`, `components/layout/AppShell.tsx`, `ProductPreviewPage.tsx`, and `PublishedMappingImports.tsx`, is SHA-256 `b99921ddb166100254eb2208a103d64ba07ce2f8478b6ea00634bd8fc5d793b8` (35 files; hash input is each relative path, NUL, UTF-8 content, NUL). This fingerprint excludes tests being finalized concurrently. Subsequent production changes require targeted re-audit.

Screenshot protection was created **before capture** at `.planning/ui-reviews/.gitignore`. Screenshots are in `.planning/ui-reviews/04-20260906-audit/`: search, detail and constraint-dialog images at 320, 375, 768, 1024 and 1440px; additional 320px loading, options error, detail error and post-write refresh error images. Settled dialog captures wait for the existing entrance animation to finish. The test context requested reduced motion throughout.

The existing `frontend/e2e/translations.spec.ts` passed **13/13** against this current-source server. It proves desktop/mobile search, cursor retry, detail/Back restoration, role affordances and the constraint mutation/conflict cycle. Passing those assertions does not prove the computed styles, error focus, or motion behavior below. Native browser 200% zoom and current-build admin screenshots were not captured; do not claim those checks passed. Backend import execution and real deployment smoke remain separate delivery gates.

## Pillar Scores

| Pillar | Score | Key Finding |
|---|---:|---|
| 1. Copywriting | 3/4 | Filtered-empty criteria print transport enum values instead of the approved visible labels. |
| 2. Visuals | 3/4 | Current navigation has no visible distinction; important refresh-error copy is ellipsized. |
| 3. Color | 2/4 | Focused filter text has 3.24:1 contrast; loading uses 30 accent-colored skeletons. |
| 4. Typography | 2/4 | Actual control and dialog typography diverges from the four-size/two-weight contract. |
| 5. Spacing | 2/4 | Shell gutters resolve to 21/28px; the numeric field and search retry are below 44px. |
| 6. Experience Design | 2/4 | Detail errors lose heading/focus recovery, options states omit search, and reduced motion is ignored. |

No score is averaged upward. No complete task-blocking defect was reproduced; all findings below are **WARNING**, consistent with scores 2–3. The core workflows passing does not make the visual contract complete.

## Top 3 Priority Fixes

1. **C-01 — Correct selected-option/hover contrast.** Product keyboard selection currently places `#111827` on `#0F766E` at 12.25px, measured contrast **3.24:1**. Use the approved neutral option/secondary-control treatment with the teal focus ring, or a validated contrasting foreground where an accent surface is explicitly allowed. Check all five filters, base-language options and outline/ghost actions.
2. **E-01 — Restore accessible detail error recovery.** Keep the route's `Translation details` h1 mounted during loading, absence and failure; focus the owning Alert after an explicit failed retry. A 503 and repeated Retry currently leave zero h1 elements and focus on BODY.
3. **T-01 — Apply the declared typography in the rendered primitives.** Remove conflicting inherited `text-sm`, `text-lg`, `font-medium` and `leading-none` defaults from the components used here, or supply reliable contract-specific variants. Assert computed title 20px/600, Label 12px/600/1.3 and Body 14px/400/1.5. A `text-heading` class alone currently does not win over the inherited dialog title size.

The remaining nine findings should be corrected in the same bounded UI pass; they are not superseded by these priorities.

## Detailed Findings

### Pillar 1: Copywriting (3/4)

**WARNING CW-01 — Filter summary leaks transport vocabulary.** `frontend/src/features/translations/TranslationSearchPage.tsx:229` builds visible Active criteria from raw `state`, `violation` and `deleted` values. Examples include `Length status: no_max` and `Deleted status: all`, while the contract declares `No max length` and `Active and deleted`. Reuse the same display-label mapping as `TranslationFilters.tsx:52` for the summary. This is a source-proven mismatch; the normal result-list screenshot does not exercise the filtered-empty branch.

Positive evidence: search purpose, explicit empty/error prose, `Open details`, inheritance, save/remove confirmations and retained/no-dataset import prose match the named contracts. `MaximumLengthDialog.tsx:106` uses consequence-specific removal copy; `PublishedMappingImports.tsx:249` distinguishes retained data from no created dataset. Raw source text is rendered as text nodes, not error prose or executable markup.

### Pillar 2: Visuals (3/4)

**WARNING V-01 — Current destination is only programmatic.** `frontend/src/components/layout/AppShell.tsx:121` calculates the active route and sets `aria-current` at line 138, but the Button class at line 132 has no current-state treatment. In `search-1440.png`, Workspace, Translations and all admin destinations share the same teal text, white background and weight. Add an explicit visible current state, retaining `aria-current` and the existing all-role ordering. Verify both desktop navigation and the mobile Sheet.

**WARNING V-02 — Important mutation outcome is clipped.** `frontend/src/components/ui/alert.tsx:42` defaults every AlertTitle to `line-clamp-1`. `MaximumLengthDialog.tsx:276` inherits it for `Maximum length saved; current details could not be loaded`. At 320px the title has clientHeight 18px and scrollHeight 35px; `mutation-refresh-error-320.png` visibly ends with an ellipsis. This hides part of the distinction between a saved mutation and a failed refresh. Remove the clamp for these bounded recovery messages and permit wrapping; check initial/load-more/detail errors too. The parser alert already explicitly uses `line-clamp-none` at `PublishedMappingImports.tsx:422`.

Positive evidence: populated search has a clear page title and flat separated collection; detail preserves section hierarchy and typed selectors. All five sampled viewport widths contained the page without horizontal scrolling. The list mounted 9–12 rows from 50 loaded groups; excerpt clamping stayed confined to result previews.

### Pillar 3: Color (2/4)

**WARNING C-01 — Focused option contrast is inadequate.** `frontend/src/components/ui/select.tsx:110` uses `focus:bg-accent focus:text-accent-foreground`; `frontend/src/index.css:47` maps the accent foreground to primary dark text. Opening Product focuses an option with measured foreground `rgb(17,24,39)` and background `rgb(15,118,110)` at every sampled width: relative-luminance contrast **3.24:1**, below the 4.5:1 normal-text criterion. `button.tsx:16` and line 20 reuse that color pair for outline/ghost hover; update those affected states as well. Preserve a distinct visible keyboard focus treatment.

**WARNING C-02 — Loading spends the accent on an entire collection.** `frontend/src/components/ui/skeleton.tsx:7` uses `bg-accent`; `TranslationSearchPage.tsx:49` creates five rows × six Skeletons. The initial options state contains **30 teal blocks**, confirmed by computed `rgb(15,118,110)` in `options-loading-320.png`. The contract reserves accent for navigation, focus, links and the primary constraint action; a skeleton is none of those. Use a neutral skeleton surface. The populated screenshot alone would miss this substantial accent overuse.

**WARNING C-03 — Secondary and warning surfaces diverge from declared tokens.** Search/filter containers at `TranslationSearchPage.tsx:244` and `TranslationFilters.tsx:83` have no white Secondary region; dialogs inherit `bg-background` at `dialog.tsx:64` and `alert-dialog.tsx:59`, measured `#F8FAFC` instead of the declared white dialog surface. The detail violation alert at `TranslationDetailPage.tsx:328` introduces `amber-600/50/950` instead of the existing warning token. Use the approved Secondary region/dialog surface and warning token treatment, preserving readable text and neutral secondary controls. The 60/30/10 contract is assessed through these concrete declared allocations, not an invented exact screenshot pixel ratio.

No local hex literals are necessary to create these mismatches: inherited Tailwind colors can break the contract even when feature files use token-looking class names. Registry configuration remains official-only.

### Pillar 4: Typography (2/4)

**WARNING T-01 — Existing shadcn defaults are not aligned with the approved type roles.** The relevant source fingerprint contains eight size-class families (`text-xs`, `text-sm`, `text-base`, `text-lg`, `text-label`, `text-body`, `text-heading`, `text-display`) and three weight families (`font-regular`, `font-medium`, `font-semibold`). Computed measurements, rather than the class inventory alone, prove the discrepancy:

| Element | Actual | Required |
|---|---|---|
| Search/filter labels | 12.25px, 500, line-height 12.25px | Label 12px, 600, line-height 15.6px |
| Filter option/trigger text | 12.25px | Body 14px |
| Clear search / Clear filters | 12.25px, 500 | Declared Body/Label role and only 400/600 |
| Set maximum length dialog title | 15.75px, 600 | Heading 20px, 600 |
| Dialog description | 12.25px, 400 | Body 14px, 400 |

Sources: `label.tsx:14`, `select.tsx:38` and line 110, `button.tsx:8`, `dialog.tsx:128` and line 141, consumed by `MaximumLengthDialog.tsx:379`. The root HTML font size is 14px, so inherited rem sizes no longer resolve to their commonly assumed pixel sizes. Fix the primitive/variant typography intentionally; do not change the root size alone, which could disturb all existing spacing. Recheck actual styles after class merging and CSS ordering. Page Display 28px/600 and feature section Heading 20px/600 do measure correctly.

### Pillar 5: Spacing (2/4)

**WARNING S-01 — Rem-based shell and dialog spacing misses the approved scale.** `AppShell.tsx:337` uses `px-6 md:px-8` with a 14px root. Computed page gutters are **21px below 768px and 28px from 768px**, against the contract's explicit **24px/32px**. Dialog `p-6` measures **21px**, while its inherited `gap-4` measures 14px rather than the declared 16px dialog spacing. Use `--space-lg`, `--space-xl` and `--space-md` for the relevant shell/dialog rules, including alert-dialog variants. The feature result row already uses the correct 16px token; detail sections use the correct 24px token.

**WARNING S-02 — Several actual controls miss the minimum target size.** Search-error `Retry search` at `TranslationSearchPage.tsx:80` inherits default `h-9`, measured **31.5px** at 320px. `MaximumLengthDialog.tsx:393` does not override the Input's `h-9` (`input.tsx:11`), which also resolves to 31.5px before entrance transforms. Base-language menu options at `ProductPreviewPage.tsx:482` omit the search filters' `min-h-[44px]` override. Apply a minimum 44px height and sufficient width to these concrete mobile/coarse-pointer controls and verify computed hit boxes. The search/filter triggers, detail links, navigation destinations and primary dialog buttons do meet 44px in the audit browser.

### Pillar 6: Experience Design (2/4)

**WARNING E-01 — Detail loading/absence/error lack route heading and retry focus.** The only detail h1 lives inside `LoadedDetail` (`TranslationDetailPage.tsx:306`). Error and loading branches at lines 494 and 521 omit it; the error Alert has no ref/tabIndex/focus management. Mocking `GET /api/v1/translations/group-0` to 503 produces **zero h1** and BODY focus, both initially and after pressing `Retry details`. Keep one route heading across all states and focus only current, user-triggered failure feedback. Add a regression for failed explicit retry and preserve the prohibition on stale/background focus stealing.

**WARNING E-02 — Options loading/failure removes the search field.** The ready branch owns the entire search input at `TranslationSearchPage.tsx:244`; the not-ready branch at line 464 renders only disabled filters and loading/error output. A held options request and then 503 both contain **zero `#translation-query`** elements. A product-scope change can therefore remove the entered query/control while reauthorizing language options. Keep the labeled query and existing value visible, with a deliberate loading state, while only unavailable option-dependent controls remain disabled. Retry should preserve the current query and restore sensible focus.

**WARNING E-03 — Reduced motion is requested but not respected.** With Playwright `reducedMotion: 'reduce'`, skeletons retain a **2s infinite pulse**, and the opened search Select retains a **0.15s entrance animation**. `skeleton.tsx:7`, `select.tsx:63`, `dialog.tsx:42`/64 and `alert-dialog.tsx:59` have animation utilities without corresponding reduced-motion overrides in these usages. Disable those decorative animations/transitions under reduced motion; retain all state completion and focus behavior. `ProductPreviewPage.tsx:480` already demonstrates the explicit `motion-reduce:animate-none` pattern. The existing E2E suite requests reduced motion but does not assert these computed animation properties.

Positive evidence: all-role read-only detail, admin/reviewer-only mutation affordances, pending duplicate/dismissal guards, explicit conflict replacement, retained input, non-optimistic authority, literal mixed-direction text, opaque links and Back focus/scroll restoration passed the 13 browser cases. Import/parser source enforces the five-issue cap, Keys-before-Translations ordering, safe fixed categories, retained/no-dataset prose and admin-only base-language recovery; preview uses exact detected-language options and backend confirmation authority.

## UI consideration coverage

The existing inventory in `frontend/e2e/translations.spec.ts:11` enumerates **50 instances across eight categories**; its three open axes are network loss, request/response without live updates, and reduced motion. Counting that inventory is not equivalent to validating every instance visually.

| Category | Audit result |
|---|---|
| Empty | Named empty/missing values and no-rule states exist; CW-01 affects filtered-empty summary labels. |
| Loading | First/append/detail states exist; E-02 removes the query, C-02 overuses accent, E-03 leaves animation enabled. |
| Error | Safe bounded copy and mutation recovery exist; E-01 lacks heading/focus, V-02 clips an important outcome. |
| Populated | Search/detail/constraint browser journey passed; V-01, T-01 and C-01 affect visible presentation. |
| Partial | Mixed/violation metadata and retained dataset paths are explicit; parser and optional-detail variants are primarily source/test evidence. |
| Overflow | Sampled widths fit; V-02 still clips an error title. Native 200% zoom remains unverified. |
| Zero-one-many | Singular/plural result copy, bounded virtual DOM and parser cap exist; not every cardinality was visually captured. |
| Long text | Hostile markup, Unicode, multiline target and long paths rendered literally and wrapped in browser. |

Network-loss/constraint conflict recovery was exercised by the existing browser suite and additional 503 probes. No live-update or offline authority was added. Reduced-motion compliance is explicitly **not** passed because of E-03.

## Reproduction

No installation is needed; use the already installed frontend dependencies.

```sh
cd /Users/smutti/Documents/personal/verboflex/frontend
./node_modules/.bin/vite --host 127.0.0.1 --port 4175 --strictPort
```

From another terminal, the audit driver retained at `/tmp/verboflex-ui-audit.mjs` uses the existing `detail`, `summary` and `setup` fixtures from `frontend/e2e/translations.spec.ts`, transpiles them in memory, intercepts generated API calls, prints computed measurements, and captures the screenshots listed above:

```sh
node /tmp/verboflex-ui-audit.mjs
cd /Users/smutti/Documents/personal/verboflex/frontend
PLAYWRIGHT_BASE_URL=http://127.0.0.1:4175 PLAYWRIGHT_OUTPUT_DIR=/tmp/verboflex-ui-audit-e2e ./node_modules/.bin/playwright test e2e/translations.spec.ts
```

The driver is temporary local audit tooling, not committed project code. Relevant printed records are `SEARCH`, `OPTION`, `DIALOG`, `DETAIL ERROR`, `RETRY ERROR`, `LOADING`, `OPTIONS ERROR`, `MAX INPUT`, and `MUTATION ERROR`. For the numeric field, inspect CSS height or wait until the entrance animation settles before using the transformed bounding box. Contrast uses the standard sRGB relative-luminance formula on the measured foreground/background pair.

## Registry Safety

Registry audit: **0 third-party blocks checked, no flags**. `frontend/components.json` has `registries: {}` and the approved UI-SPEC declares no third-party registries. No registry fetch/install/diff was applicable. TanStack Virtual is the separately approved non-registry logic dependency.

## Files Audited

- Contract/context: `04-UI-SPEC.md`, `04-CONTEXT.md`; Phase 04 PLAN inventory 01–27 and available SUMMARY inventory 01–18/21–27, particularly UI implementation plans/summaries 09, 16–18 and 22–24. Plan 19/20 closure is independent of this audit.
- `frontend/src/features/translations/TranslationSearchPage.tsx`, `TranslationFilters.tsx`, `TranslationResultList.tsx`, `TranslationDetailPage.tsx`, `MaximumLengthDialog.tsx`, `TranslationsWorkspace.tsx`, `useTranslationSearch.ts`, `translationDetailAuthority.ts`, `translationPreferences.ts` and their relevant component/controller tests.
- `frontend/src/features/admin/previews/ProductPreviewPage.tsx` and base-language cases in `ProductPreviewPage.test.tsx`; `frontend/src/features/admin/imports/PublishedMappingImports.tsx` and parser/retained-dataset cases in `PublishedMappingImports.test.tsx`.
- `frontend/src/components/layout/AppShell.tsx`, `frontend/src/router.tsx`, `frontend/src/index.css`; shared Button, Input, Label, Select, Alert, Dialog, AlertDialog, Badge, Skeleton and Tooltip presentation used by the audited routes.
- `frontend/e2e/translations.spec.ts`, `frontend/playwright.config.ts`, `frontend/package.json`, `frontend/components.json`.

**Recommendation count:** 3 priority fixes; 9 additional recommendations; 12 distinct findings total. Re-run the affected measurements and journeys after correction before replacing these scores.
