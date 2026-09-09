# Changelog

## 1.3.0 — early public release, 2026-09-09

- Added the owner-approved MIT licence for original source code and documentation, with separate public-sample and promotional-media notices.
- Reworked the English README around the first-use workflow, qualitative-analysis outputs, local data handling and honest support boundaries.
- Included the public-only English product tour, captions, cover and a separately packaged editable video project.
- Extended the local privacy guard to detect service secret keys and credential assignments, with exact-checksum promotional-media exceptions and additional regression coverage.
- Human acceptance, clean-machine setup and target qualitative-software imports remain open testing items; this is not a production-readiness certification.

- Added an isolated public-media practice launcher, ten-step interactive acceptance checklist, and local test-record download.
- Bundled the attributed CC BY-SA public sample with a checksum-restricted media exception, an in-app beginner guide, and a written first-run walkthrough.
- Reopening practice preserves active transcription; initial loading no longer briefly shows an empty workspace.
- Added an original vector logo and accessible narrow-screen segment browsing.
- Added draft saving, verified-segment navigation, review-history summaries, and stale-write protection.
- Protected all human edits and decisions from reprocessing, including unclear and pending drafts.
- Fixed empty caption edits reverting to source wording during export and timed-word leakage into silent windows.
- Unified individual and packaged change reports; protected workbook overview cells from formula interpretation; included raw cue JSON in packages.
- Strengthened staged-content and reachable-history privacy checks with regression tests.
- Clarified same-model dual-pass limitations, empty-project status, approximate splitting, and export review-status semantics.

All notable changes to Transcript Review Studio are documented here.

## 1.2.0 — 2026-09-03

### Added

- In-app video/audio preview with cue seek, looping, speed, and context controls.
- Reviewer name or initials stored per project and written to human action records.
- Likely source-VTT omissions recovered from either local STT pass and surfaced as `missing_source` cues.
- Visible previous/next attention controls when the queue sidebar is hidden.
- API regression coverage for local-origin controls, private file boundaries, attribution, rejected VTT cleanup, draft export gating, Unicode filenames, and CSV formula escaping.
- Product, architecture, user, privacy, contribution, and release documentation.
- A documented public-media end-to-end regression using a licensed five-minute group discussion.

### Changed

- Migrated the interface to standard local Next.js scripts and removed hosting-specific build dependencies.
- Replaced probability-like confidence wording with heuristic recognition-score wording.
- Empty or incomplete work is no longer described as verified; synchronized exports use `draft` filenames until every cue is verified.
- Export schema terminology is distinct from product and transcript review status.
- Setup recreates an isolated Python virtual environment and validates prerequisites.
- Data directories and files are hardened to owner-only Unix permissions.

### Fixed

- Long recording names stay within the recording sidebar.
- Unsaved cue edits are protected when navigating.
- Splitting a cue no longer leaves stale editor text that could overwrite the split result.
- Every unresolved cue is directly selectable in long attention queues, and JSON is visible alongside the other export formats.
- Invalid source captions and speaker tracks are rejected without orphaning partial imports.
- Unicode recording names download safely.
- Rejected cross-site browser requests and database paths outside the private project directory are blocked.

### Security

- Updated FastAPI, Starlette transitively, python-multipart, and Uvicorn to versions with no vulnerabilities reported by the release audit.
- Added npm and Python dependency audits to the release gates.

## 1.1.0 — 2026-08-28

- Added qualitative-analysis DOCX, NVivo DOCX, XLSX, structured CSV, metadata, audit, provenance, manifest, and checksum exports.
- Added named isolated speaker-track support and the three-version human review workflow.
