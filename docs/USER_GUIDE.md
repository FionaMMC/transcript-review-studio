# User Guide

## Before you begin

Use the current release on an Apple Silicon Mac. You need:

- Python 3.11 or newer.
- Node.js 22.13 or newer.
- FFmpeg and FFprobe (`brew install ffmpeg` when using Homebrew).
- Free disk space for source media, a normalized audio copy, dependencies, and model weights.
- Authorization to store and review the research material on this computer.

The first model run can access Hugging Face to download weights. The application does not upload the recording or transcript for recognition.

## Install and open

1. Download or clone the dedicated Transcript Review Studio repository. Do not put it inside another product repository or a participant-data folder.
2. Double-click `Setup Transcript Review Studio.command`. macOS may require Control-click → Open the first time.
3. Wait for `Setup complete`. The script creates an isolated Python environment, installs exact application dependencies, installs the interface, and runs validation.
4. Double-click `Open Transcript Review Studio.command`.
5. Keep the launcher window open. Closing it stops the local services but does not delete work.

If port 3000 or 8765 already belongs to another application, the launcher stops and reports the conflict rather than connecting to an unknown service.

For your first session, use **Try Transcript Review Studio.command** instead. It opens the bundled public discussion in a separate practice workspace on port 8766. Follow the in-app **Getting started** guide or the [beginner walkthrough](GETTING_STARTED.md) before importing research material.

## Create a project and set attribution

Create or select a project, then enter your name or initials in **Reviewer**. The value belongs to the project and is attached to subsequent verify, unclear, and split actions. If it is blank, actions remain usable but are recorded as `Not recorded`.

## Import and process

1. Select the original video or audio.
2. Give the recording a concise research-safe name.
3. Optionally select the original VTT. It must contain at least one timed cue.
4. Optionally add isolated participant tracks and confirm their speaker labels.
5. Choose the spoken language. Automatic detection is convenient; an explicit language can reduce recognition errors.
6. Keep **Alternate-context second pass** enabled when you want a second comparison. Both passes use the same model and can share errors; they are not independent evidence.
7. Choose **Import & process locally** and wait for the recording to become ready.

Processing is serialized to avoid competing memory-heavy models. Reprocessing is blocked after any human review action, including saved drafts, unclear decisions, and splits. Re-import the original into a new recording if you need a fresh transcription while preserving reviewed work.

## Verify efficiently

The selected cue controls the media preview. Listen before accepting any wording or speaker.

| Control | Result |
|---|---|
| `Space` | Play or pause the active cue. |
| `1` / `2` / `3` | Copy Source VTT / STT A / STT B into the editor. |
| `↑` / `↓` | Move through the current attention queue. |
| `U` | Save as unclear and advance. |
| `Command–Return` | Save as verified and advance. |
| `−5 s` / `+5 s` | Hear context around the cue. |
| Loop cue | Replay the current segment during listening. |
| Save draft | Store the current edit as pending without certifying it. |
| Browse → Verified segments | Reopen a previously verified segment. |
| Review history | Inspect the selected segment's saved actions and reviewers. |
| Split at playhead | Divide an overlong cue; both halves return to pending. |

Leaving a cue, recording, project, or workflow stage with edits in the editor prompts before discarding them. Recognition scores are prioritisation signals only. A high score does not make a word correct, and a low score does not prove it is wrong.

Use **Mark unclear** when the audio cannot justify a transcription. Do not guess. Adopt and document a team convention such as `[inaudible 00:12:34]` when appropriate.

## Export for qualitative analysis

Individual formats are useful for quick handoff. The complete package is the archival and reproducible handoff:

- DOCX speaker-turn transcript for reading, quotation, and common CAQDAS import.
- NVivo DOCX table with Timespan, Speaker, Content, Segment ID, and Review Status.
- XLSX plus segment- and turn-level CSV for framework analysis and reproducible scripts.
- VTT/SRT for media-synchronized review; TXT for broad portability.
- English before/current change log and report.
- Review history, provenance, metadata, data dictionary, transcription conventions, manifest, and checksums.

If any cue remains pending, flagged, or unclear, synchronized files are named `draft`. Per-segment review status is included in the structured exports and package metadata; SRT cannot carry it. Only a nonempty, all-verified recording receives `verified` filenames. A verified label records your review decisions, not an independent accuracy certification.

The default package excludes original media but still contains sensitive transcript material. **Include original media** creates a restricted package; confirm the destination is approved for identifiable audio/video.

## Back up and restore

Close the launcher, then copy the entire folder below to an approved encrypted destination:

```text
~/Library/Application Support/Transcript Review Studio
```

Do not copy only `studio.sqlite3`: media paths and project folders are part of the same dataset. To restore, close the app and restore the entire folder to the same path. Keep backups out of GitHub and ordinary consumer sync folders unless your study approval explicitly allows them.

## Troubleshooting

- **Setup says Python, Node, or FFmpeg is missing:** install the named prerequisite and rerun Setup.
- **Local service unavailable:** close other copies, run the launcher again, and keep its terminal window open.
- **No speech-recognition engine:** confirm this is an Apple Silicon Mac and rerun Setup while online.
- **First transcription appears idle:** the model may be downloading; inspect the launcher window and allow time and disk space.
- **Processing interrupted:** choose **Try again**. Existing complete cue data remains transactionally stored.
- **No transcript cues:** confirm the recording contains audible speech and the media is not corrupt; try an explicit language or a valid source VTT.
- **Wrong speaker:** named tracks are only evidence. Select the correct speaker manually before verification.
- **A download says draft:** return to Human verification and resolve every pending, flagged, or unclear cue.

Never paste participant text or attach source media to a public issue. Report software problems with synthetic examples and redacted logs only.
