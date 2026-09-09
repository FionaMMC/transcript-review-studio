# Product Definition

## Product promise

Transcript Review Studio helps a researcher turn local interview or focus-group media into a traceable, human-checked transcript without uploading participant data. Automation narrows the review surface; a human remains accountable for every verified cue.

## Primary users

- Researchers and research assistants reviewing interviews, focus groups, usability sessions, or field recordings.
- Teams that must keep identifiable media on an approved local computer.
- Analysts who need readable transcripts plus structured, reproducible data for NVivo, MAXQDA, ATLAS.ti, spreadsheets, or scripts.

The product assumes the user understands their study's consent, data-management, retention, and disclosure obligations.

## Core jobs

1. Preserve the original media and optional source captions as evidence.
2. Generate two local recognition passes with different decoding context.
3. Align source and machine versions, including likely speech omitted by the source VTT.
4. Prioritise disagreements, missing versions, low recognition scores, timing drift, and source omissions.
5. Let the reviewer listen, compare, edit, label the speaker, adjust timing, and save quickly.
6. Preserve attributable before/after actions without silently rewriting transcript content during export.
7. Export clear `draft` or `verified` outputs with metadata, conventions, provenance, and checksums.

## End-to-end state model

| Object | State | Meaning |
|---|---|---|
| Recording | `imported` | Local files are stored and media was validated. |
| Recording | `processing` | Local extraction, recognition, alignment, or speaker-track analysis is running. |
| Recording | `ready` | Cues exist or processing completed with no cues; human review can begin. |
| Recording | `error` | Processing stopped; the error is shown and retry is available. |
| Cue | `pending` | Generated or imported but not explicitly checked by a human. |
| Cue | `flagged` | Evidence conflict requires attention. |
| Cue | `unclear` | A human listened but could not resolve the wording; it remains unresolved. |
| Cue | `verified` | A human explicitly saved the current text, speaker, and timing as verified. |

The project is complete only when every recording is ready and has cues, and every cue is `verified`. Empty, unprocessed, and partially reviewed projects must never be presented as complete.

## Key interaction contract

- Selecting another cue, recording, project, or workflow stage must not silently discard unsaved edits.
- The video or audio preview must seek to the selected cue and support replay, looping, speed changes, and nearby context.
- The source VTT, local pass A, and local pass B are evidence, not truth. Recognition scores are heuristics, not calibrated probabilities.
- Saving a cue creates an audit record with reviewer name or `Not recorded`.
- Splitting a cue leaves both resulting cues unresolved.
- Reprocessing is blocked after any manual edit or review decision, including drafts and unclear cues. Cue revisions reject stale writes from another window.
- Automatic speaker diarization, automatic anonymisation, analytic coding, and cloud collaboration are not implemented.

## Output contract

Every export uses current workspace wording without linguistic cleanup. Reading and structured formats normalize whitespace; raw JSON and audit entries preserve saved text. If any cue is unresolved, synchronized transcript files are named `draft`; only fully reviewed transcripts are named `verified`. Per-segment status is retained in structured outputs, not spoken-caption text. The full package includes:

- Reading and coding documents (`analysis_transcript.docx`).
- NVivo-oriented timespan tables (`nvivo_transcript.docx`).
- Structured workbooks and UTF-8 CSV files with stable IDs.
- VTT, SRT, and TXT representations.
- A complete English before/current comparison.
- Review actions, processing provenance, data dictionary, transcription conventions, manifest, and SHA-256 checksums.

Original media is excluded by default. Including it creates a restricted package and requires a deliberate confirmation.

## Product quality measures

- No participant data or transcript text is required in the source repository or test suite.
- Every completion claim is derived from cue state, never from recording count alone.
- A reviewer can move between attention cues without a hidden queue sidebar.
- Every release passes frontend lint/build, backend unit/API tests, dependency audits, and manual browser checks of the critical workflow.
- A fresh supported Mac can install and launch using the two `.command` files and the documented prerequisites.

## Explicit non-goals for 1.2

- Certifying that machine transcription is correct without human listening.
- Identifying speakers biometrically or inferring identity from voice.
- Automatically anonymising direct or indirect identifiers.
- Replacing a CAQDAS system for coding, memos, cases, or interpretation.
- Multi-user synchronization, cloud hosting, or institutional access control.
