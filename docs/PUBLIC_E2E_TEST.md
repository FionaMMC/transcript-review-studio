# Public-media end-to-end test

Test date: 3 September 2026

This is the historical 1.2 test record. See [Release review](RELEASE_REVIEW.md) for the 1.3 checks and current limitations.

## Fixture and licence

The test uses *Preliminary discussions regarding Lua bot framework*, a five-minute English group discussion recorded at a Lua Workshop. Jim Carter published the original recording on Wikimedia Commons under the Creative Commons Attribution-ShareAlike 4.0 International licence.

- Source and attribution: <https://commons.wikimedia.org/wiki/File:Preliminary_discussions_regarding_Lua_bot_framework.webm>
- Licence: <https://creativecommons.org/licenses/by-sa/4.0/>
- Current Wikimedia image-info SHA-1: `02d75482a9cd04aee4ba883d1cc93ab2f0b70f2d`
- Downloaded size: 30,857,519 bytes
- Media: 300.003 seconds, VP8 1920×1080 video, stereo Vorbis audio

At the time of this test, the media, machine transcripts, exports, and test database were excluded from the repository. In 1.3 the owner approved bundling this exact public video with attribution and a pinned checksum. Generated transcripts, exports, and databases remain excluded.

## Test design

The public recording was imported through the browser interface into a temporary `TRS_DATA_DIR`. The run selected English, enabled both local STT passes, supplied no source VTT, and supplied no isolated speaker tracks. This exercises the difficult no-reference, far-field group-discussion path without touching the real research database.

## Results

- Import, FFprobe validation, audio extraction, two local STT passes, alignment, and ambiguity scoring reached `ready` in 69 seconds from the recorded import and completion timestamps.
- The pipeline produced 160 valid, monotonically indexed cues covering the five-minute recording.
- STT A populated 160 cues; alternate-context STT B populated 157. Both passes use the same model, not independent evidence. The three missing B segments were explicitly flagged as `missing_version`.
- The queue identified 52 word disagreements, 22 timing-drift cases, 16 low-recognition-score cases, and 3 missing-version cases. Mean heuristic ambiguity was 29.4/100.
- Browser playback reached ready state 4 and advanced after the user-facing **Play cue** action. HTTP byte-range serving returned `206` with the requested 1,024 bytes.
- The comparison view displayed Source, STT A, and STT B separately. Both generated passes contained text, and manual speaker entry remained available.
- An attributable `Public QA` review action successfully marked one segment unclear and remained present in the audit log.
- All ten individual export endpoints returned `200`: DOCX, NVivo DOCX, XLSX, CSV, JSON, TXT, VTT, SRT, change list, and change report.
- The default qualitative package contained 19 files. Office/ZIP integrity checks and every SHA-256 manifest entry passed. Original media was absent by default.
- The export interface correctly labelled the package as draft, exposed the restricted-with-media option, and had no browser console warnings or horizontal overflow.

## Findings resolved during the run

1. The attention queue previously rendered only its first 80 segments even though navigation and totals covered the full recording. The cap was removed so every filtered cue is directly selectable.
2. JSON was available through the API but missing from the export interface. A visible JSON download was added.

## Interpretation and limitation

This run validates product integration and failure visibility; it does not establish transcription accuracy. The Commons recording has no human reference captions, so word error rate and speaker-attribution accuracy cannot be calculated. Speaker labels appropriately remain manual because generic diarization is not implemented. A separate corpus benchmark with aligned human ground truth is required before making quantitative accuracy claims.
