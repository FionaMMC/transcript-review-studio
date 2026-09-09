"""Prepare an isolated, reusable public-media practice workspace (never private data)."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import sys
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRACTICE_DIR = Path.home() / "Library" / "Application Support" / "Transcript Review Studio Practice"
SOURCE_URL = "https://upload.wikimedia.org/wikipedia/commons/1/1f/Preliminary_discussions_regarding_Lua_bot_framework.webm"
SOURCE_PAGE = "https://commons.wikimedia.org/wiki/File:Preliminary_discussions_regarding_Lua_bot_framework.webm"
SOURCE_SHA1 = "02d75482a9cd04aee4ba883d1cc93ab2f0b70f2d"
ATTRIBUTION = (
    "Preliminary discussions regarding Lua bot framework — Jim Carter. "
    "CC BY-SA 4.0: https://creativecommons.org/licenses/by-sa/4.0/ . "
    "Video unmodified. Practice VTT is machine-generated with seeded wording changes; "
    "it is not a reference transcript. Keep this attribution with redistributed derivatives."
)


def has_existing_workspace() -> bool:
    database = PRACTICE_DIR / "studio.sqlite3"
    if not database.is_file():
        return False
    # Preparing an already-open workspace must not run startup recovery, which
    # would mark the running service's transcription job as interrupted.
    with sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True) as db:
        table = db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'projects'").fetchone()
        return bool(table and db.execute("SELECT 1 FROM projects LIMIT 1").fetchone())


def prepare() -> None:
    os.umask(0o077)
    # Deliberately ignore a caller's TRS_DATA_DIR: practice must never target research data.
    os.environ["TRS_DATA_DIR"] = str(PRACTICE_DIR)
    os.environ["TRS_PRACTICE"] = "1"
    if has_existing_workspace():
        print("Practice workspace already exists; all of your practice edits are preserved.")
        return
    sys.path.insert(0, str(ROOT / "backend"))
    from transcript_review.database import connection, initialize, utc_now
    from transcript_review.processing import probe_media, process_recording
    from transcript_review.vtt import to_vtt

    initialize()
    material = PRACTICE_DIR / "practice-material"
    material.mkdir(parents=True, exist_ok=True)
    sample = material / "public-discussion.webm"
    bundled = ROOT / "samples" / "lua-workshop" / "public-discussion.webm"
    if not sample.exists() and bundled.is_file():
        if hashlib.sha1(bundled.read_bytes()).hexdigest() != SOURCE_SHA1:
            raise RuntimeError("The bundled public sample failed its checksum. Obtain a clean project copy.")
        shutil.copy2(bundled, sample)
        print("Using the public video bundled with this repository. No media download is needed.", flush=True)
    if not sample.exists():
        print("Downloading the public Wikimedia sample (about 30 MB). No files are uploaded.", flush=True)
        partial = material / "public-discussion.part"
        request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "TranscriptReviewStudio/1.3 (local research practice)"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as output:
                shutil.copyfileobj(response, output)
            if hashlib.sha1(partial.read_bytes()).hexdigest() != SOURCE_SHA1:
                raise RuntimeError("The public sample has changed. Check its attribution and checksum before using it.")
            partial.replace(sample)
        finally:
            partial.unlink(missing_ok=True)
    if hashlib.sha1(sample.read_bytes()).hexdigest() != SOURCE_SHA1:
        raise RuntimeError("The existing public sample checksum does not match. No project was created.")
    (material / "ATTRIBUTION.md").write_text(f"# Public practice material\n\n{ATTRIBUTION}\n\nSource: {SOURCE_PAGE}\n", encoding="utf-8")
    project_id, recording_id = uuid.uuid4().hex, uuid.uuid4().hex
    recording_dir = PRACTICE_DIR / "projects" / project_id / "recordings" / recording_id
    media = recording_dir / "media" / sample.name
    media.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sample, media)
    info = probe_media(media)
    now = utc_now()
    with connection() as db:
        db.execute("INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)", (project_id, "Public sample · hands-on review", now, now))
        db.execute("""INSERT INTO recordings (id, project_id, name, media_path, duration_ms, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (recording_id, project_id, "Lua workshop discussion · practice baseline", str(media), info["duration_ms"], json.dumps(info), now, now))
    print("Running both local speech-recognition passes. The first use may download model weights.", flush=True)
    process_recording(recording_id, language="en", dual_pass=True)
    with connection() as db:
        recording = db.execute("SELECT * FROM recordings WHERE id = ?", (recording_id,)).fetchone()
        if recording["status"] != "ready":
            raise RuntimeError("Local processing stopped. Reopen the practice workspace and choose Try again; the imported public video is safe.")
        cues = [dict(row) for row in db.execute("SELECT * FROM cues WHERE recording_id = ? ORDER BY cue_index", (recording_id,))]
        if not cues:
            raise RuntimeError("No speech segments were generated. Inspect the local model setup.")
        for index, cue in enumerate(cues):
            source = cue["stt_a_text"]
            if index % 20 == 0 and source:
                words = source.split()
                words[len(words) // 2] = "[practice-error]"
                source = " ".join(words)
            reasons = json.loads(cue["ambiguity_reasons"])
            if source != cue["stt_a_text"] and "word_disagreement" not in reasons:
                reasons.append("word_disagreement")
            cue["final_text"] = source
            db.execute("UPDATE cues SET source_text = ?, final_text = ?, ambiguity_reasons = ?, status = ? WHERE id = ?", (source, source, json.dumps(reasons), "flagged" if reasons else "pending", cue["id"]))
        source_path = recording_dir / "source" / "practice-baseline.vtt"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(to_vtt(cues).replace("WEBVTT\n", f"WEBVTT\n\nNOTE {ATTRIBUTION}\n", 1), encoding="utf-8")
        metadata = json.loads(recording["metadata_json"])
        metadata["public_sample"] = {"source": SOURCE_PAGE, "attribution": ATTRIBUTION, "baseline": "STT A with one seeded error every 20 cues; not human-verified"}
        db.execute("UPDATE recordings SET source_path = ?, metadata_json = ? WHERE id = ?", (str(source_path), json.dumps(metadata), recording_id))
    print(f"Practice is ready: {len(cues)} segments, none human-verified. Research data was not opened.")


if __name__ == "__main__":
    prepare()
