# Phase 4: Localization Import, Search, and Constraints - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-04
**Phase:** 4-Localization Import, Search, and Constraints
**Areas discussed:** Strutture specifiche dei formati, Identità e refresh, Ricerca ed elenco risultati, Vincoli di lunghezza

---

## Strutture specifiche dei formati

### Content coverage

| Option | Description | Selected |
|--------|-------------|----------|
| Valori semplici e strutturati | Import ordinary strings, Android/Qt plurals and variants, Android arrays, and nested JSON string leaves. | ✓ |
| Solo stringhe semplici | Import scalar key/value content only and reject structured values. | |
| Supporto intermedio | Import simple strings, plurals, and nested JSON while leaving arrays and other variants unsupported. | |

**User's choice:** Import simple and structured values in v1.
**Notes:** Plural variants are preserved without adding plural-validation rules in this phase.

### Result grouping

| Option | Description | Selected |
|--------|-------------|----------|
| Raggruppati per chiave e lingua | Show one expandable key/language group while keeping every value individually addressable. | ✓ |
| Una riga per variante | Show every plural, array item, or variant as an independent result. | |
| Raggruppati per chiave su tutte le lingue | Put all languages and variants under one key result. | |

**User's choice:** Group by key and language.
**Notes:** The canonical model still needs a distinct identity for every structured value.

### Variant identity

| Option | Description | Selected |
|--------|-------------|----------|
| Chiave originale più selettore strutturato | Preserve the original key and store plural/index/variant information separately. | ✓ |
| Chiavi sintetiche appiattite | Produce dotted or bracketed synthetic keys. | |
| Identità native per formato | Keep unrelated identity conventions for each format. | |

**User's choice:** Preserve the original key plus a structured selector.
**Notes:** Searching a key must find the complete key/language group.

### Parser failure boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Fallire atomicamente l'intero mapping | Preserve the last successful dataset and publish none of the invalid candidate. | ✓ |
| Saltare solo le voci non valide | Import valid entries and omit invalid ones. | |
| Escludere l'intero file | Import other files while dropping the invalid file. | |

**User's choice:** Fail the complete mapping import atomically.
**Notes:** Present a bounded error list and retain the last usable dataset.

---

## Identità e refresh

### Key identity and rename behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Stable across file moves | Repository, branch, and key define the logical identity; file and position remain locators. | ✓ |
| File-bound identity | Moving a key creates a new identity. | |
| Automatic rename inference | Infer a rename from content and context similarity. | |

**User's choice:** “La chiave rimane legata al repository e al branch”; a renamed key is deleted and a new key appears.
**Notes:** VerboFlex never renames a key. Adding and deleting keys through VerboFlex was clarified as a future capability, not Phase 4 scope.

### Deleted-key visibility

| Option | Description | Selected |
|--------|-------------|----------|
| Hidden normally, available by filter | Retain context and expose deleted identities through a dedicated filter. | ✓ |
| Always visible | Show deleted identities in ordinary results with a badge. | |
| Audit only | Retain in storage but make unavailable to the UI. | |

**User's choice:** Hide deleted keys from normal search but keep them filterable.
**Notes:** Review state, comments, constraints, and provenance remain attached.

### External translation changes

| Option | Description | Selected |
|--------|-------------|----------|
| Update and return to Draft | Accept the source value, preserve context/history, and require review again. | ✓ |
| Preserve review state | Accept the source value without changing Approved/Rejected/Draft. | |
| Manual reconciliation | Keep the prior value until a person resolves the difference. | |

**User's choice:** An externally modified translation returns to Draft.
**Notes:** Comments, constraints, and prior state history are preserved.

### VerboFlex PR merge recognition

| Option | Description | Selected |
|--------|-------------|----------|
| Preserve Approved on exact receipt | Recognize the exact tracked VerboFlex change as synchronized rather than external. | ✓ |
| Always return to Draft | Treat every imported source change as external. | |
| Another rule | Define a different merge-state transition. | |

**User's choice:** Preserve Approved when the merged value is the exact VerboFlex-submitted value.
**Notes:** A divergent merged value returns to Draft. Phase 4 prepares correlation data; later phases execute the PR flow.

### Source-text changes

| Option | Description | Selected |
|--------|-------------|----------|
| Return all target translations to Draft | Preserve translated values and context but require review against the new source. | ✓ |
| Preserve all states | Show source-change information without changing review state. | |
| Separate needs-review flag | Add a new status independent from Draft/Approved/Rejected. | |

**User's choice:** Return every related translation to Draft.
**Notes:** Existing text, comments, and constraints remain available.

---

## Ricerca ed elenco risultati

### Initial product scope

| Option | Description | Selected |
|--------|-------------|----------|
| Last product plus All products | Restore the last authorized product while allowing cross-product search. | ✓ |
| Product required | Show no results until a product is chosen. | |
| All products initially | Begin every session with a global search scope. | |

**User's choice:** Restore the last product and provide All products.
**Notes:** Remembered state is convenience only and cannot grant product access.

### Search matching

| Option | Description | Selected |
|--------|-------------|----------|
| One field over key and texts | Case-insensitive key/source/translation search with exact and prefix ranking first. | ✓ |
| Separate fields | Provide separate key, source-text, and translated-text inputs. | |
| Fuzzy search | Accept misspellings and approximate matches. | |

**User's choice:** One search field, no fuzzy matching in v1.
**Notes:** Exact results precede prefixes, which precede partial matches.

### Initial language scope

| Option | Description | Selected |
|--------|-------------|----------|
| Last language plus All languages | Restore the last available language and permit a cross-language view. | ✓ |
| Language required | Show no results until a language is selected. | |
| All languages initially | Show every key/language combination immediately. | |

**User's choice:** Restore the last language and provide All languages.
**Notes:** Results remain grouped by key and language.

### Result loading

| Option | Description | Selected |
|--------|-------------|----------|
| Cursor pages | Use explicit next/previous page controls. | |
| Virtualized infinite scrolling | Load cursor-backed results as the user scrolls without accumulating an unbounded DOM. | ✓ |
| Numbered offset pages | Use page numbers and offset-based navigation. | |

**User's choice:** Virtualized infinite scrolling.
**Notes:** The backend owns deterministic ordering and cursor stability; filter changes invalidate prior cursor chains.

---

## Vincoli di lunghezza

### Scope and inheritance

| Option | Description | Selected |
|--------|-------------|----------|
| One value for every language | Apply one key-level maximum to all translations. | |
| Per-language values with base default | Let target languages override a dynamically inherited base-language value. | ✓ |
| Product default with key exceptions | Apply a product-wide default and override it by key. | |

**User's choice:** One value per language, defaulting to the base language.
**Notes:** Languages without an override follow future base-limit changes dynamically; explicit overrides remain unchanged.

### Character measurement and byte limits

| Option | Description | Selected |
|--------|-------------|----------|
| Visible Unicode characters | Count extended grapheme clusters so composed characters and combined emoji count once. | ✓ |
| Unicode code points | Count underlying scalar values even when several form one visible character. | |
| Encoded bytes | Count storage size, which varies by encoding. | Deferred |

**User's choice:** Count visible Unicode characters in Phase 4 and add a later phase for byte limits.
**Notes:** The user highlighted kanji and memory-constrained systems. A later `max_bytes` constraint must name its encoding because the same character has different byte sizes in UTF-8 and UTF-16.

### Mutation authority

| Option | Description | Selected |
|--------|-------------|----------|
| Admin and Product manager/reviewer | Operational owners manage constraints; Translator and Viewer read them. | ✓ |
| Admin only | Centralize every constraint mutation. | |
| Include Translator | Allow translators to modify constraints too. | |

**User's choice:** Admin and Product manager/reviewer may mutate constraints.
**Notes:** Translator and Viewer retain read access.

### Violation behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Draft allowed, approval/submission blocked | Permit iterative work but prevent violating content from progressing. | ✓ |
| Warning only | Permit approval and submission despite the violation. | |
| Block saving | Reject any over-limit text immediately. | |

**User's choice:** A violation can remain Draft but cannot be approved or submitted.
**Notes:** Phase 4 exposes authoritative violation state; later workflow phases enforce their mutation gates.

---

## the agent's Discretion

- Exact persistence schema, parser interfaces, typed selector representation, stable UUID derivation, indexes, cursor encoding, virtual-list implementation, page size, overscan, tie-break ordering, and bounded error copy.
- Storage location for last product/language convenience preferences, provided server-side authorization is always authoritative.
- Exact configuration/storage point for the mapping's base language; it must resolve deterministically and fail closed if missing or ambiguous.

## Deferred Ideas

- Add and delete localization keys through VerboFlex in a later phase; direct key rename remains excluded.
- Add a dedicated later phase for `max_bytes` constraints with explicit file or mapping encoding.
