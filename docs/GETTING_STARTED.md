# Your first transcript in Transcript Review Studio

Learn with the public sample before importing research data. This walkthrough uses the exact controls in the application. You do not need an account or a cloud speech API key.

## 1. Set up and open the sample

On an Apple Silicon Mac, install Python 3.11+, Node.js 22.13+, and FFmpeg. Run **Setup Transcript Review Studio.command** once, then open **Try Transcript Review Studio.command**.

The five-minute discussion is already in `samples/lua-workshop/public-discussion.webm`. The practice launcher copies it to its own data folder and runs two local recognition passes. Model weights may download on first use; wait until the recording is ready. Keep the launcher window open.

You should see **Practice workspace**, **Public sample · hands-on review**, and the **Getting started** guide. Your real research projects are not used in this mode.

## 2. Understand the three versions

| What you see | What it means | How to use it |
|---|---|---|
| Source VTT | The baseline supplied with a recording. In this practice workspace it is generated from STT A and contains labelled practice errors. | Compare it with the sound, not just the other text. |
| Local STT A | A context-aware machine transcription. | A candidate reading, never ground truth. |
| Local STT B | The same model with a different decoding context. | Helps expose disagreements; agreement still does not prove accuracy. |
| Transcript editor | The current wording you will save and export. | Choose **Use** for a candidate, then type any correction. |

Numbers labelled **ambiguity** prioritize attention; they are not an accuracy percentage. Speaker identity must be checked manually. This sample does not include named isolated speaker tracks.

## 3. Listen, compare, and change a word

1. Click **Hide guide** when you want more room for the video.
2. Click **Play cue**. Use **Loop cue**, **−5 s**, **+5 s**, and **Speed** to hear context. Choosing another cue seeks the player to that segment.
3. Find `[practice-error]` in the first baseline cue. This marker was inserted deliberately for the exercise; it was not spoken.
4. Listen. If one machine version matches what you hear, click **Use** beside it. Otherwise type your own wording in **Transcript editor**.
5. Do not invent an answer when the sound is unclear. Keep an uncertainty marker according to your research team's conventions and use **Mark unclear**.

## 4. Choose the right save action

Enter your initials in **Reviewer**. These are attached to subsequent review actions; adding a name later does not retrospectively identify old actions.

| Action | Result |
|---|---|
| **Save draft** | Stores the working text without claiming that you checked it. The segment remains pending. |
| **Mark unclear** | Stores the edit as unresolved and moves on. Use it for an ambiguity you cannot settle. |
| **Save & next** | Explicitly certifies your review of the current text, speaker, and timing and moves to the next unresolved cue. Use only after listening. |
| **Review history** | Shows the action, reviewer, and time for the selected segment. Full before/after evidence is in the export audit files. |

To revisit finished work, choose **Browse → Verified segments**, then **Go to** a segment. **All segments** includes both finished and unfinished work. Changing a cue does not discard an unsaved draft without a confirmation. Another window's newer save is protected by a revision check; copy your draft and reload if there is a conflict.

## 5. Adjust a boundary if needed

Change **Start** and **End** in seconds, or position the player and choose **Set start** / **Set end**. To divide a segment, move the playhead inside its time range and click **Split at playhead**.

Splitting divides the text approximately. Listen to both pieces, adjust their wording, and verify them separately. Both pieces return to pending; the audit history retains the earlier evidence.

## 6. Export something you can inspect

Open **Resolve & export** and choose **Download draft analysis package**. It is a draft until all segments are reviewed. You do not need to finish all sample segments to learn the export workflow; the exact count can vary with local processing.

Unzip the package and begin with:

- `README.md`: package structure, review status, and confidentiality notes.
- `*_analysis_transcript.docx`: readable speaker turns for research coding.
- `*_analysis_workbook.xlsx`: filterable Turns, Segments, and Change Log worksheets.
- `*_change_log.csv`: complete English before/current comparison, stable IDs, and reviewer attribution.
- `*_review_actions.jsonl`: the full saved action history.
- `*_draft.vtt` / `*_draft.srt`: timed captions. Keep the metadata with them; SRT does not carry review status.

The default package excludes original media, **not** sensitive transcript content. Before sharing any real research export, review identities, consent, licensing, and storage permissions. The **Include original media** option is restricted and requires a deliberate confirmation.

## 7. Try your own import

Stay in practice mode and create another project. Open **Import & process**, select the bundled sample, optionally select a source `.vtt`, enter a recording name, choose the language, and click **Import & process locally**.

Without a VTT, the model creates the starting transcript. All generated segments still require review. Named isolated audio tracks are optional; ordinary automatic speaker diarization is not available in this release.

When you are comfortable, close the practice launcher and use **Open Transcript Review Studio.command** for your research workspace. Follow the [User Guide](USER_GUIDE.md) for backup and recovery. Never copy real research files into the source repository.

## Ready to help us test?

Switch to **Acceptance checklist** in the practice guide and complete the ten checks. Download your test record and share only nonsensitive findings with the project maintainer. See [Manual acceptance](MANUAL_TEST.md) and [sample attribution](../samples/lua-workshop/README.md).
