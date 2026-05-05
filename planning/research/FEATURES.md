# Feature Research

**Domain:** Bitbucket-backed localization review and approval portal
**Researched:** 2026-05-04
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Product and repository configuration | Products use different repositories, branches, formats, and translation layouts. | HIGH | Must support direct translations and key-repo to translation-repo mappings. |
| Branch-aware import | Localization work follows product release branches. | MEDIUM | Source branch should be configured per repository/project. |
| Multi-format parsing | Known products use Android XML, Qt `.ts`, JSON, and iOS `.strings`. | HIGH | Each format needs parser, canonical mapper, writer, and fixtures. |
| Search and filters | Product managers need to find strings without navigating Bitbucket. | MEDIUM | V1 filters: product, language, key/text, approval state, constraint violations. |
| Translation detail view | Reviewers need source text, target translation, language, state, comments, constraints, and file context. | MEDIUM | Build with shadcn/ui primitives such as sheet/dialog, tabs, textarea, badges, tooltips, and toast. |
| Edit translations | Authorized users need to fix text in the portal. | MEDIUM | Edits should create pending change sets, not immediately write to Bitbucket. |
| Simple review states | Draft, approved, rejected are enough to make review actionable. | LOW | Keep state history/audit even if workflow rules are simple. |
| Translation comments | Comments reduce ambiguity and capture review discussion. | MEDIUM | Store comments per translation in the app. |
| Max length constraint | UI and embedded products often have strict text limits. | MEDIUM | Constraint should be stored per string and evaluated per language translation. |
| Constraint violation filters | Reviewers need to triage strings that cannot ship. | LOW | Length checks should be recalculated after edits and imports. |
| Internal users and roles | Admins must control who can configure, edit, approve, comment, or view. | MEDIUM | Users can have multiple roles. |
| Bitbucket write-back | The repository remains source of truth. | HIGH | Create branches/commits and PRs according to per-project config. |
| PR status and audit trail | Users need to know what happened after submission. | MEDIUM | Store commit hash, PR URL/id, source/target branches, author, and included strings. |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Flexible cross-repository mapping UI | Handles products where keys and translations live in different Bitbucket projects. | HIGH | This is central to the user's domain and differentiates from simpler file upload tools. |
| Product-specific PR behavior | Fits existing development workflows instead of forcing one PR strategy. | MEDIUM | Supports one PR per repo/branch/session based on project config. |
| Constraint-aware review | Product managers can focus on translations that violate product/UI rules. | MEDIUM | V1 only max length, but model should allow later validators. |
| Source-of-truth preserving writes | Keeps Bitbucket as the authoritative system while improving review UX. | HIGH | Requires careful parser/writer and stale-branch handling. |
| Project-owned UI component system | Allows dense review/admin screens to be customized without fighting a black-box UI library. | MEDIUM | Use shadcn/ui generated code as the frontend design-system base. |
| Future Figma context | Links translations to screens for better review. | HIGH | Defer until core repository workflow is proven. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Full translation management suite in v1 | Sounds complete compared with Crowdin/Phrase/Lokalise/Weblate. | Too broad; glossary, MT, memory, jobs, agencies, and Figma would bury the core workflow. | Build repository-backed review/approval first. |
| Auto-discover every repository mapping | Reduces admin setup. | Cross-repo key/translation relationships are product-specific and risky to infer. | Explicit admin mapping UI with validation previews. |
| Direct commits to protected target branches | Faster than PRs. | Bypasses development workflow and branch protections. | Always create PRs for v1 write-back. |
| Complex approval gates in v1 | Enterprise workflows often want them. | User selected simple states; gates can be layered after usage is known. | Store enough audit data to add gates later. |
| Figma integration before repository workflow | Gives UI context early. | It does not validate the core source-of-truth loop. | Defer Figma to a later phase. |

## Feature Dependencies

```text
Product/repository config
    -> branch config
        -> import scanner
            -> format parsers
                -> canonical translation records
                    -> search and review UI
                        -> edits/comments/states
                            -> change sets
                                -> Bitbucket branch/commit/PR

Constraints
    -> canonical translation records
        -> violation detection
            -> review filters

Internal users/roles
    -> admin config permissions
    -> edit/approve/comment permissions

Cross-repo mapping
    -> import scanner
    -> write-back routing
```

### Dependency Notes

- **Repository config requires branches:** imports and PRs must be branch-aware from the start.
- **Parsers require canonical model:** search/review should not be hardwired to individual file formats.
- **Change sets require parser/writer fixtures:** writing to Bitbucket before preserving file semantics is unsafe.
- **Roles gate all mutating actions:** admin, edit, approve, comment, and submit actions must have explicit authorization checks.

## MVP Definition

### Launch With (v1)

- [ ] Product/repository/branch configuration - required to connect Bitbucket source data.
- [ ] Cross-repo key/translation mapping configuration - required for known product structures.
- [ ] Four file format readers/writers - Android XML, Qt `.ts`, JSON, iOS `.strings`.
- [ ] Canonical translation search - required for product manager workflow.
- [ ] Translation review detail - required to inspect, edit, comment, and see constraints.
- [ ] Draft/approved/rejected states - required for review decisions.
- [ ] Per-translation comments - explicitly required by user.
- [ ] Max length constraints and violation filters - required for UI/technical fit.
- [ ] Internal users with multiple roles - required for authorization.
- [ ] Bitbucket branch/commit/PR creation - required for source-of-truth workflow.

### Add After Validation (v1.x)

- [ ] Import/job dashboard - add once background imports exist and need operational visibility.
- [ ] PR update/resubmit workflow - add after first PR creation path is proven.
- [ ] Bulk state changes - useful after reviewers handle larger datasets.
- [ ] File preview before PR - useful for confidence and reviewer trust.

### Future Consideration (v2+)

- [ ] Figma screen linking - deferred design context.
- [ ] Placeholder, plural, forbidden-character, and line-count validators - deferred constraint expansion.
- [ ] External identity provider integration - deferred enterprise auth.
- [ ] Configurable role gates and per-product approval policies - deferred workflow sophistication.
- [ ] Translation memory, machine translation, glossary, and terminology checks - outside v1.
- [ ] Bitbucket Server/Data Center support - outside v1.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Product/repository config | HIGH | HIGH | P1 |
| Branch-aware import | HIGH | MEDIUM | P1 |
| Parser/writer support for four formats | HIGH | HIGH | P1 |
| Canonical search/filter | HIGH | MEDIUM | P1 |
| Translation detail + edit | HIGH | MEDIUM | P1 |
| Simple states | HIGH | LOW | P1 |
| Comments | HIGH | MEDIUM | P1 |
| Max length constraints | HIGH | MEDIUM | P1 |
| Internal roles | HIGH | MEDIUM | P1 |
| Bitbucket branch/commit/PR | HIGH | HIGH | P1 |
| Job dashboard | MEDIUM | MEDIUM | P2 |
| Bulk operations | MEDIUM | MEDIUM | P2 |
| Figma context | HIGH | HIGH | P3 |

## Competitor Feature Analysis

| Feature | Lokalise | Crowdin | Weblate/Phrase | Our Approach |
|---------|----------|---------|----------------|--------------|
| Bitbucket sync | Pull/push language files with Bitbucket integration. | Sync source files and create pull requests. | Git/API integrations and branch workflows are common. | Bitbucket Cloud-only, PR-based source-of-truth workflow. |
| Review and approval | Approved files can be pushed back. | Reviewers/proofreaders approve translations. | Review workflows and comments are common. | Simple draft/approved/rejected states with app comments. |
| File formats | Broad format support. | 100+ formats and mobile app formats. | Broad localization file support. | Start with four known formats only. |
| Context | Preview, comments, design integrations. | Screenshots, comments, glossaries, Figma. | Context/comments are common. | Store comments in v1; defer Figma. |
| Constraints/QA | QA and file preview. | Length limits/placeholders/QA checks. | Quality checks. | Max length only in v1; extensible validator model later. |

## Sources

- [Lokalise Bitbucket integration](https://lokalise.com/product/apps/code-repositories/bitbucket/) - Bitbucket sync, approved files, branch behavior.
- [Crowdin platform overview](https://crowdin.com/) - Git integrations, file formats, QA checks, branch-based translation management, comments/context, PR workflow.
- [Weblate features](https://weblate.org/en/features/) - comments, context, multiple formats, branch support, reviews.
- [Weblate project configuration docs](https://docs.weblate.org/en/latest/admin/projects.html) - review workflow, branch components, file format configuration, VCS update behavior.
- [Phrase Strings overview](https://phrase.com/platform/strings/) - key-based software localization, comments/context, approval workflows, file formats, development workflow integrations.

---
*Feature research for: VerboFlex*
*Researched: 2026-05-04*
