---
task: 260906-kjj
type: quick
status: executing
gap_ids: [G-04-1]
---

# UAT remediation and safe product deletion

Read SPEC.md in this directory. User explicitly approved v1; also verify babel importability read-only before assuming its layout is supported.

1. RED/GREEN draft-only and inactive published import composition; deterministic preview-budget reproduction and optional bounded localization root/error diagnostics across mapping, preview and import.
2. RED/GREEN administrator logical product deletion, confirmation dialog, name reuse, protected reads/mutations and worker concurrency; reversible/fail-safe migrations.
3. Fresh regression/coverage/type/lint/mutation/property/browser/security checks, evidence, backed-up Docker upgrade, and UAT retest handoff. Preserve prior reports as historical; never auto-pass live human checks.

Run sequentially on codex/merge-phases-4-5. No remote writes, push or merge. No new dependencies proposed. Keep the user's existing product and provider configuration intact.

## 2026-09-06 implementation checkpoint

S1/S2 frontend correction implemented with RED/GREEN regression tests; see EVIDENCE.md. Root propagation and deletion remain approved but unimplemented. Live Babel inspection additionally found 42,766 string elements and 145 repeated occurrences within eight files; the canonical mapping limit is 5,000 values. MOKO addendum approval is recorded, but it explicitly preserves that budget and duplicate rejection. Pause the MOKO import claim at this contract boundary: no automatic limit increase, deduplication, remote data edits or fabricated import success. Full task and Phase 4 UAT remain incomplete; Docker has not been rebuilt for this checkpoint.

## 2026-09-06 requested extension

User requested fixing import capacity and a UI mode exposing duplicate keys. Proposed SPEC-IMPORT-CAPACITY-DUPLICATES.md records the larger bounded mapping capacity and read-only, blocking diagnostic-mode semantics. Await approval of that revised contract under old-coder; do not treat the user's new requirement as approval of an unseen SPEC. Resume this existing quick task (do not create the new directory suggested by the context-only init.quick call). Implementation order after approval: root/MOKO/capacity and worker diagnostics → additive report API/UI → fresh integration/scale/security/deployment checks; retain the already-approved deletion task, without asking to approve it again.

## 2026-09-06 approved extension implementation (supersedes the historical wait above)

Approval recorded in 7f5a934. Root, bounded MOKO/capacity, worker-stored diagnostic API/UI, streaming manifests and batched initial activation implemented; full backend/frontend regression suites pass at the source digest in EVIDENCE.md. This is a GREEN regression checkpoint, not a completed quick task or release. Remaining work includes timeout coordination, complete all-format diagnostics and summary projections, refresh/search scale, root/UI authority edges, S5 discovery messaging, logical deletion, missing changed-line/mutation/browser/security gates and backed-up Docker upgrade. Babel currently has 145 duplicate groups plus additional unsupported escape/inter-element-text semantics; surface the latter before extending interpretation. No new approval is needed for the already-approved remaining slices.

## 2026-09-06 MOKO semantic direction

The user confirmed the direction to preserve unknown escapes and inter-element source text. `SPEC-MOKO-SEMANTICS.md` now makes the exact MOKO-only behavior, lossless edit obligation and retained rejection boundaries reviewable. Per the old-coder approval rule, the direction given before this document is input rather than approval of the unseen executable contract. Pause implementation until the user explicitly approves that file; all unrelated previously approved remaining slices stay approved.
