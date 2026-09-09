# Manual acceptance test

Status: **the owner must complete this test before a public release**. Automated checks do not certify usability or transcript accuracy.

## Open a safe practice workspace

After running Setup, double-click **Try Transcript Review Studio.command**. It uses the 5-minute public discussion bundled under `samples/lua-workshop`, performs two real local transcription passes, and opens `http://127.0.0.1:3000/?practice=1`. In the guide choose **Acceptance checklist**. A download fallback exists for source copies without the sample.

The practice database and media are stored in `~/Library/Application Support/Transcript Review Studio Practice`, separate from the research workspace. The practice backend listens on loopback port 8766; the normal backend uses 8765. The launcher never replaces an existing practice project. Reopening it preserves your edits.

The initial baseline is generated from STT A with one explicitly labelled `[practice-error]` inserted every 20 cues. This is a workflow exercise, **not** a transcription accuracy benchmark or a human reference. Both decoding passes use the same model and may agree on errors.

## Your checklist

The app contains the same interactive checklist, including a local Markdown download of your results. Allow about 15 minutes plus model processing time.

- [ ] Play, pause, loop, seek ±5 seconds, and change playback speed. Check picture/sound alignment.
- [ ] Compare Source VTT, STT A, and STT B. Listen and correct a seeded error.
- [ ] Enter reviewer initials; save a draft, reopen it, and confirm it is still pending.
- [ ] Verify a cue only after listening. Revisit it using **Browse → Verified segments** and inspect **Review history**.
- [ ] Mark another cue unclear; confirm it remains unresolved.
- [ ] Type an unsaved edit, select another cue, and cancel the discard prompt. Confirm nothing was lost.
- [ ] Split a cue at an interior playhead position. Check both texts/timings; both must require review.
- [ ] Download the default draft analysis package. Inspect DOCX, XLSX, English before/after records, manifest, and status. Confirm no original media is included.
- [ ] Download the public sample from the checklist. Create another practice project and import it without a source VTT. Observe real local processing and confirm all generated cues need human review.
- [ ] Save, reload or restart, and confirm your work survives.

Record failures with the step, expected behavior, observed behavior, operating system, browser, and app version. Use public or synthetic data only in screenshots and GitHub issues.

## Additional release checks

A second researcher should test installation on a fresh Apple Silicon Mac. Test importing the exported DOCX/VTT in the actual versions of NVivo, MAXQDA, or ATLAS.ti used by your team. This repository does not claim vendor certification or tested compatibility with every CAQDAS release.

## Public sample attribution

“Preliminary discussions regarding Lua bot framework”, Jim Carter, 15 October 2016. [Wikimedia Commons source](https://commons.wikimedia.org/wiki/File:Preliminary_discussions_regarding_Lua_bot_framework.webm), [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

The source video bytes are unmodified; the generated practice baseline contains seeded wording changes. Preserve attribution and apply the sample's licence when redistributing adaptations. The app's MIT licence does not replace the sample's licence. The tutorial includes this checksum-pinned public source recording; separately reviewed promotional assets are documented in `docs/media`. Private transcripts and research media are not included.
