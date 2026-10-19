# New keys, plurals and translation reuse

Implemented in the October 2026 authoring update. The UI, REST API and MCP connector
share the same version, role and repository-authority checks.

## Create keys and complete translations

Open a product's **Strings** workspace and choose **New key**. Select a confirmed
repository file, language and type, enter the key and translation, then **Save**.
The entry appears under **New entries**, where reviewers can approve or reject it.
An existing missing language has **Add translation**; native plural rows also have
**Add forms**. Imported empty values use the existing translation editor.

New entries are versioned drafts, separate from imported coverage. Save does not
write to Git. Approved entries join the existing change-set preparation and
Bitbucket pull-request workflow. Every preparation checks the mapping, source file
hash, key identity, character limits and latest draft version. A refresh marks
older drafts as source-changed; reopen and save them against the current file.
A successful import consumes additions whose exact values are now in the repository.
Parent-key deletion physically removes attached additions.

| Format | Creation support |
| --- | --- |
| Android XML | Strings and `<plurals>`; missing quantities; native escaping. |
| Qt TS | ID-based or source/context-based messages; ordered `numerus` forms. |
| JSON | Scalar properties inside an existing object; explicit parent path. |
| iOS `.strings` | Scalar entries, preserving the file's encoding. |

Each draft targets one existing mapped file and language. Choose the base-language
file to create the source resource. Other languages can be added separately.
Qt requires source text and context. For JSON, enter the parent path as a JSON
array, such as `["menu", "actions"]`; those parent objects must already exist.
Writers insert only the new resource and reparse the result to verify that existing
values and the requested identities remain intact.

Files, file templates, source-key creation in a separate keys repository, converting
an existing scalar to a plural, ICU/JSON plural dialects, Apple `.stringsdict` and
XLIFF writeback are outside this release. Public GitHub projects support local
creation/review; GitHub publication is still unavailable.

## Qt source text and the base catalog

Qt catalogs keep `<source>` and `<translation>` separately, including in the
configured base-language file. The workspace displays embedded **Source text**
separately from editable translations. The catalog locale does not establish the
language of each source phrase: a project can mix Italian and English sources.
Saving a translation preserves the source and its message identity. By default,
**Needs translation** includes empty Qt translations even in the base catalog.

Administrators can open **Product configuration → product overview → Source language
settings**, enable **Use confirmed source text for the base language**, and select
exact source phrases already written in that language. For those phrases only,
empty scalar Qt translations display the source with **Using source text** and
leave both search representations of **Needs translation**. The policy is scoped
to the product and base locale, independent of mapping revisions and imports.
Other products keep their own settings. Updates are audited, version checked,
and invalidate existing search cursors.

The selection is explicit: there is no language guessing or automatic translation.
Foreign phrases, new or changed source text, plurals and length variants remain
eligible for translation. An actual imported translation or a current proposal
takes precedence over fallback. The policy never fills repository files, creates
proposals, approves changes or opens pull requests. Saving an explicit translation
still uses the regular review workflow. Disabling the policy restores the original
empty-translation behavior. Product coverage continues to measure target languages,
excluding the configured base locale.

The multilingual built-stack smoke configures this policy through the administrator
interface, verifies its persistence and filtering, then saves/reloads a translation
for a foreign source without changing either imported field.

## Native plurals

Android quantities come from Babel 2.17 / CLDR 46 cardinal categories. Qt forms
follow the Qt 6.10 Linguist order, which differs from CLDR category order. For
example, Qt uses two forms for Italian, one for Vietnamese and six for Arabic.
Unknown Qt profiles fail with an explicit error.

The editor displays the required forms for the selected language. Drafts can be
incomplete; approval requires the complete family, including already imported
forms in the same context. Qt argument markers must match the source. Character
limits apply to every form, with red counters and fields when exceeded. This
release does not include a numerical plural preview or runtime-profile selector.

## Reuse while editing

The **Suggestions** panel sits beside the active translation on wide screens and
below it on narrow screens. It shows:

- Exact matches first (100%), followed by similar matches with a textual score.
- Source differences, translation, originating key, file and repository.
- **Approved draft** or **Repository**, so imported text is not mistaken for approval.
- **Use**, which checks the current suggestion again and copies it into the draft.

Nothing is saved or approved by **Use**. If the suggestion changed, disappeared,
or the user typed while it was being checked, application is refused. The draft
keeps the normal Save/Cancel and length-limit behavior.

Matches are scoped to the current project, language pair, file format and compatible
selector/form. No cross-project sharing, automatic propagation, cross-format
placeholder conversion or AI provider is involved. The panel applies one form at a
time. Qt markers, printf argument positions/types and simple brace placeholders are
checked; unsupported nested/ICU interpolation is excluded from suggestions.

The panel reads current imported values and current approved proposals. Draft,
rejected and stale proposals never override repository text. There is no historical
translation-memory copy: deleted canonical content immediately stops being eligible.
At most 20 distinct suggestions are returned, from bounded candidate queries.
Inputs and suggestion texts are limited to 4,096 characters; lookups have a 1.5-second
statement timeout. SHA-256 and the existing Unicode trigram index support matching.
This design follows Lokalise's inline exact/fuzzy interaction, not its retention model.

## Glossary

Choose **Glossary** in a product's Strings workspace. Reviewers and admins can add,
edit and delete terms; translators and viewers can read them. Set source and target
languages, the source term, preferred or forbidden translation, optional case
sensitivity and a short note. Changes use optimistic versions and content-free
audit receipts. Deleted terms are physically removed.

Relevant terms appear in the editor. A forbidden term used in the draft is highlighted
in red. These are advisory hints: glossary violations do not block Save or approval.
Terminology is independent of repository strings and remains until explicitly removed
or its product is purged. The glossary supports 5,000 terms per project, pages of 50,
and at most 50 displayed source matches.

## API and MCP

The generated API exposes authoring destinations, plural profiles, versioned new
entries, suggestions/resolve, and glossary CRUD/matching. The MCP connector now has
70 explicitly allowed tools. Read-only connections include suggestion and term
lookups even though their bounded query payloads use HTTP POST. Creation, review,
and glossary mutation still require write permission and the user's application role.

## Verification and limits

See [application checks](application-ci.md) for automated verification and
[load testing](load-testing.md) for reproducible capacity measurements.
The local dataset check is not certification for tens of millions of strings.
Production hosting, off-host recovery and earlier release gates remain separate.

References: [Lokalise translation memory](https://docs.lokalise.com/en/articles/1409589-translation-memory),
[Android string resources](https://developer.android.com/guide/topics/resources/string-resource),
[Qt plural rules](https://doc.qt.io/qt-6/i18n-plural-rules.html),
[Unicode plural rules](https://cldr.unicode.org/index/cldr-spec/plural-rules).
