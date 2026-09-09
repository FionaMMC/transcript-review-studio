# 1.3 release-candidate review

Review date: 9 September 2026. This document records the earlier release-candidate review. The owner subsequently authorised a standalone public early release and selected MIT for the source code. The outstanding human acceptance and clean-machine checks below remain open; publication is not a claim that they have passed.

## Product decision

The product is a local human-review workspace for qualitative researchers, not an automatic transcript certification service. Its core journey is import → local recognition and comparison → listening and attributable edits → an inspectable analysis package. The supported initial platform is Apple Silicon macOS; do not advertise Windows, Intel Mac, or Linux support as tested.

The beginner experience now uses one attributed, openly licensed five-minute discussion. **Try Transcript Review Studio.command** creates a separate practice workspace, with **Getting started** and a ten-step **Acceptance checklist**. Reopening preserves edits. The original research workspace is not used by this launcher. The public sample is bundled in `samples/lua-workshop`; no generated transcript or database is bundled.

## Findings addressed

| Risk | Change | Evidence |
|---|---|---|
| Reprocessing could erase draft or unclear review work. | Protect every saved human action; recheck protection at the worker's final transaction. | Backend regression tests. |
| A stale browser could overwrite a newer cue. | Revision checks for edits and splits; editing blocked during processing; duplicate UI saves guarded. | Conflict and processing regression tests. |
| Reviewer attribution and navigation could become stale. | Use the current reviewer draft, ignore superseded project selections, and offer verified/all-segment navigation. | Regression tests and public-workspace browser exercise. |
| Empty edits or timed-word gaps could resurrect unrelated source text. | Preserve deliberately empty final text and respect timed-word windows. | Export and alignment regression tests. |
| Export metadata or spreadsheet cells could mislead readers. | Stable segment IDs and reviewer fields in direct change exports; formula-safe cells; retain raw cues; clarify draft/SRT status and same-model comparison. | Export tests and actual package inspection. |
| Private files could escape checks through staging or history. | Scan index blobs, working files, and reachable history; reviewed documents still receive content checks. Only the exact public sample path and SHA-256 are exempt from the media ban. | Synthetic privacy regression tests and release scan. |
| A newcomer lacked a safe first session. | Bundled sample, three-stage in-app walkthrough, written beginner guide, and self-reported acceptance record. | Local desktop and 390px-wide browser checks. |
| Minor interface/accessibility failures. | Constrained recording names, visible focus, readable accent foregrounds, mobile controls, and no width animation on the progress bar. | UI inspection, lint, build, and targeted design review. |

## Executed checks

- Backend/unit/privacy suite: **32 tests passed**.
- Python lint, frontend lint, TypeScript/production build: passed.
- Dependency checks: npm reported no vulnerabilities; pip-audit reported no known vulnerabilities in the pinned backend requirements. This is a point-in-time dependency check, not a security certification.
- Public sample: real local MLX Whisper processing generated **160 cues**, with both decoding passes. The exercise baseline deliberately seeds `[practice-error]` markers; it is not human ground truth.
- Browser: playback advanced with loaded audio/video; speed control, draft persistence, review attribution, and verified-segment navigation exercised. Synthetic QA edits were returned to pending; **zero cues are supplied as human-verified**.
- All **10 individual export formats** were fetched. The draft package contained **21 files**; ZIP/Office structural checks and manifest checksums passed. Original media was absent by default. Word and spreadsheet page-layout rendering was not repeated in this review.
- Desktop and narrow-screen inspection found no horizontal overflow or browser console errors in the exercised views.
- The privacy guard passed against the local candidate, including the public sample's fixed checksum. No GitHub upload was performed. The repository has no committed history yet, so the deleted-history protection was demonstrated with synthetic temporary repositories.

These checks validate specific behavior, not exhaustive correctness. Automatic browser checks are not evidence of human listening accuracy.

## Release gates still open

1. **Owner acceptance:** complete the in-app checklist. In particular, manually confirm cancel/discard behavior, timing/splitting, restart recovery, and clarity of the exported documents. Browser automation could not reliably operate the native discard dialog in this environment, so this interaction is not marked passed.
2. **Clean-machine installation:** test the downloaded repository on another Apple Silicon Mac without cached dependencies/model weights. Check first-run download, interruption/retry, available disk space, and browser codec playback.
3. **Qualitative-tool import:** import an exported sample into the actual NVivo/MAXQDA/ATLAS.ti version your colleagues use. Document formats are prepared for those workflows; compatibility with every product/version is not certified.
4. **Code licence — resolved:** the owner selected MIT for the source code on 9 September 2026. The sample's CC BY-SA 4.0 terms and the promotional narration's noncommercial terms remain separate.
5. **Publication boundary:** publish only the standalone application repository after reviewing staged files and `python3 scripts/privacy_check.py --history`. Research data, private exports, credentials and identifiable screenshots must remain excluded. Approved public-only media uses exact paths and pinned checksums. Do not publish into another product's repository.

## Known boundaries

- Both speech passes use the same model and can agree on the same error. No measured word-error rate or automatic speaker-identity accuracy is claimed.
- Generic speaker diarization is not implemented. Isolated speaker tracks are optional evidence; ordinary mixed-audio identity remains a human task.
- A local service is not a multiuser access-control system. Keep it loopback-only and use approved, encrypted OS storage and backups.
- The privacy checker is a conservative file/content guard, not a semantic anonymizer. A human still needs to review source comments, documentation, sample attribution, and any publication materials.
- Verification is an explicit reviewer decision. Draft export is allowed; media exclusion does not remove sensitive transcript content.

## Review method

The review used the existing code-review, Impeccable interface audit/polish, web-interface guidelines, end-to-end testing, and verification-before-completion skills. Work was scoped to the existing product rather than imposing a large task-decomposition framework. Regression evidence was recorded before success claims; remaining manual gates are deliberately not auto-completed.
