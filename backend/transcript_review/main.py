from __future__ import annotations

import csv
import io
import json
import mimetypes
import os
import platform
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import quote

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .compare import word_diff
from .database import (
    DATA_DIR,
    PROJECTS_DIR,
    connection,
    fetch_project,
    has_human_work,
    initialize,
    row_to_dict,
    rows_to_dicts,
    utc_now,
)
from .processing import DEFAULT_MODEL, probe_media, process_recording
from .qualitative_export import (
    CHANGE_FIELDS,
    PACKAGE_VERSION,
    PRODUCT_VERSION,
    change_report_bytes,
    change_rows,
    csv_bytes,
    export_docx_bundle,
    research_slug,
    transcript_state,
    write_project_package,
)
from .vtt import format_timestamp, parse_vtt, to_srt, to_vtt

app = FastAPI(title="Transcript Review Studio", version=PRODUCT_VERSION)
ALLOWED_ORIGINS = {"http://localhost:3000", "http://127.0.0.1:3000"}
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(ALLOWED_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def local_origin_and_privacy_headers(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        return JSONResponse(status_code=403, content={"detail": "Requests are accepted only from the local Transcript Review Studio interface."})
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    reviewer: str | None = Field(default=None, max_length=120)


class ProcessRequest(BaseModel):
    model: str = Field(default=DEFAULT_MODEL, min_length=1, max_length=120)
    language: str = Field(default="auto", pattern=r"^(auto|[a-z]{2,3})$")
    dual_pass: bool = True


class CueUpdate(BaseModel):
    expected_revision: int | None = Field(default=None, ge=0)
    final_text: str | None = Field(default=None, max_length=100_000)
    speaker: str | None = Field(default=None, max_length=120)
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=1)
    status: Literal["pending", "flagged", "verified", "unclear"] | None = None
    reviewer: str | None = Field(default=None, max_length=120)


class SplitRequest(BaseModel):
    expected_revision: int | None = Field(default=None, ge=0)
    split_ms: int = Field(ge=1)
    final_text: str | None = Field(default=None, max_length=100_000)
    speaker: str | None = Field(default=None, max_length=120)
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=1)
    reviewer: str | None = Field(default=None, max_length=120)


@app.on_event("startup")
def startup() -> None:
    initialize()


def not_found(kind: str = "Item") -> HTTPException:
    return HTTPException(status_code=404, detail=f"{kind} not found")


def safe_filename(name: str) -> str:
    name = Path(name).name.strip().replace("\x00", "")
    return "".join(character if character.isalnum() or character in " ._-()" else "_" for character in name) or "untitled"


async def save_upload(upload: UploadFile, destination: Path, *, max_bytes: int | None = None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    size_limit = max_bytes or max(1, int(os.environ.get("TRS_MAX_UPLOAD_GB", "50"))) * 1024**3
    written = 0
    try:
        with destination.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                written += len(chunk)
                if written > size_limit:
                    if size_limit >= 1024**3:
                        limit_label = f"{size_limit // 1024**3} GB"
                    else:
                        limit_label = f"{size_limit // 1024**2} MB"
                    raise HTTPException(status_code=413, detail=f"This file exceeds the {limit_label} local import limit.")
                output.write(chunk)
        if os.name != "nt":
            destination.chmod(0o600)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def managed_file(path_value: str | Path) -> Path:
    path = Path(path_value).expanduser().resolve()
    try:
        path.relative_to(PROJECTS_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="A project file points outside the private application data directory.") from exc
    return path


def content_disposition(filename: str, disposition: str = "attachment") -> str:
    """Return an ASCII-safe header while preserving Unicode download names."""
    ascii_name = "".join(character if character.isascii() and (character.isalnum() or character in " ._-()") else "_" for character in filename)
    ascii_name = ascii_name.strip(" ._") or "transcript-download"
    return f'{disposition}; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename, safe="")}'


def capability_payload() -> dict[str, Any]:
    try:
        import mlx_whisper  # noqa: F401

        mlx_available = platform.system() == "Darwin" and platform.machine() == "arm64"
    except ImportError:
        mlx_available = False
    try:
        import faster_whisper  # noqa: F401

        faster_available = True
    except ImportError:
        faster_available = False
    try:
        import pyannote.audio  # noqa: F401

        diarization_available = True
    except ImportError:
        diarization_available = False
    active_engine = "mlx_whisper" if mlx_available else ("faster_whisper" if faster_available else None)
    default_model = DEFAULT_MODEL if active_engine == "mlx_whisper" else "large-v3"
    return {
        "local": True,
        "practice_mode": os.environ.get("TRS_PRACTICE") == "1",
        "platform": f"{platform.system()} {platform.machine()}",
        "python": sys.version.split()[0],
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "ffprobe": shutil.which("ffprobe") is not None,
        "stt": {
            "mlx_whisper": mlx_available,
            "faster_whisper": faster_available,
            "active": active_engine,
            "default_model": default_model,
            "note": "Model weights may download once; inference and project data stay on this computer.",
        },
        "speaker_assignment": {
            "named_tracks": True,
            "generic_diarization": False,
            "generic_diarization_model_detected": diarization_available,
            "note": "Named isolated tracks and manual labels are supported. Generic diarization is not implemented in this release.",
        },
        "data_directory": str(DATA_DIR),
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "product": "Transcript Review Studio", "version": PRODUCT_VERSION, "capabilities": capability_payload()}


@app.get("/api/capabilities")
def capabilities() -> dict[str, Any]:
    return capability_payload()


@app.get("/api/practice/sample")
def practice_sample() -> FileResponse:
    sample = DATA_DIR / "practice-material" / "public-discussion.webm"
    if os.environ.get("TRS_PRACTICE") != "1" or not sample.is_file():
        raise not_found("Public practice sample")
    return FileResponse(sample, media_type="video/webm", filename="public-discussion.webm")


@app.get("/api/projects")
def list_projects() -> list[dict[str, Any]]:
    with connection() as db:
        projects = rows_to_dicts(db.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall())
    return projects


@app.post("/api/projects", status_code=201)
def create_project(payload: ProjectCreate) -> dict[str, Any]:
    if not payload.name.strip():
        raise HTTPException(status_code=422, detail="Project name cannot be empty.")
    project_id = uuid.uuid4().hex
    now = utc_now()
    with connection() as db:
        db.execute(
            "INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (project_id, payload.name.strip(), now, now),
        )
    (PROJECTS_DIR / project_id).mkdir(parents=True, exist_ok=True)
    return fetch_project(project_id) or {}


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    project = fetch_project(project_id)
    if not project:
        raise not_found("Project")
    return project


@app.patch("/api/projects/{project_id}")
def update_project(project_id: str, payload: ProjectUpdate) -> dict[str, Any]:
    changes = payload.model_dump(exclude_none=True)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise HTTPException(status_code=422, detail="Project name cannot be empty.")
    if "reviewer" in changes:
        changes["reviewer"] = changes["reviewer"].strip()
    if not fetch_project(project_id):
        raise not_found("Project")
    if changes:
        with connection() as db:
            fields = [f"{key} = ?" for key in changes]
            db.execute(
                f"UPDATE projects SET {', '.join(fields)}, updated_at = ? WHERE id = ?",
                [*changes.values(), utc_now(), project_id],
            )
    return fetch_project(project_id) or {}


@app.post("/api/projects/{project_id}/recordings", status_code=201)
async def import_recording(
    project_id: str,
    media: Annotated[UploadFile, File(...)],
    source_vtt: Annotated[UploadFile | None, File()] = None,
    speaker_tracks: Annotated[list[UploadFile] | None, File()] = None,
    speaker_names: Annotated[list[str] | None, Form()] = None,
    recording_name: Annotated[str | None, Form(max_length=160)] = None,
) -> dict[str, Any]:
    if not fetch_project(project_id):
        raise not_found("Project")
    recording_id = uuid.uuid4().hex
    recording_dir = PROJECTS_DIR / project_id / "recordings" / recording_id
    media_name = safe_filename(media.filename or "media")
    media_path = recording_dir / "media" / media_name
    await save_upload(media, media_path)
    try:
        media_info = probe_media(media_path)
    except Exception as exc:
        shutil.rmtree(recording_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Could not read the media file: {exc}") from exc

    source_path: Path | None = None
    track_rows: list[tuple[str, str]] = []
    try:
        if source_vtt and source_vtt.filename:
            source_path = recording_dir / "source" / safe_filename(source_vtt.filename)
            await save_upload(source_vtt, source_path, max_bytes=25 * 1024**2)
            try:
                source_cues = parse_vtt(source_path.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail=f"Could not read the source VTT: {exc}") from exc
            if not source_cues:
                raise HTTPException(status_code=400, detail="The source VTT does not contain any timed captions.")

        for index, track in enumerate(speaker_tracks or []):
            if not track.filename:
                continue
            track_path = recording_dir / "speaker-tracks" / f"{index + 1:02d}-{safe_filename(track.filename)}"
            await save_upload(track, track_path)
            try:
                probe_media(track_path)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Could not read speaker track {track.filename}: {exc}") from exc
            supplied_name = speaker_names[index].strip() if speaker_names and index < len(speaker_names) else ""
            speaker = (supplied_name or Path(track.filename).stem)[:120]
            track_rows.append((speaker, str(track_path)))
    except Exception:
        shutil.rmtree(recording_dir, ignore_errors=True)
        raise

    now = utc_now()
    display_name = (recording_name or "").strip() or Path(media_name).stem
    metadata = {**media_info, "named_speaker_tracks": [row[0] for row in track_rows], "processing_is_local": True}
    try:
        with connection() as db:
            db.execute(
                """
                INSERT INTO recordings (
                    id, project_id, name, media_path, source_path, duration_ms, status,
                    processing_stage, processed_percent, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'imported', 'Ready to process', 0, ?, ?, ?)
                """,
                (
                    recording_id,
                    project_id,
                    display_name,
                    str(media_path),
                    str(source_path) if source_path else None,
                    media_info["duration_ms"],
                    json.dumps(metadata),
                    now,
                    now,
                ),
            )
            db.executemany(
                "INSERT INTO speaker_tracks (recording_id, speaker, path) VALUES (?, ?, ?)",
                [(recording_id, speaker, path) for speaker, path in track_rows],
            )
            db.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, project_id))
    except Exception:
        shutil.rmtree(recording_dir, ignore_errors=True)
        raise
    project = fetch_project(project_id)
    assert project
    return next(item for item in project["recordings"] if item["id"] == recording_id)


@app.post("/api/recordings/{recording_id}/process", status_code=202)
def start_processing(recording_id: str, payload: ProcessRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    if payload.model not in {DEFAULT_MODEL, "large-v3", "turbo"}:
        raise HTTPException(status_code=422, detail="Unsupported local speech-recognition model.")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        recording = db.execute("SELECT id, status FROM recordings WHERE id = ?", (recording_id,)).fetchone()
        if not recording:
            raise not_found("Recording")
        if recording["status"] == "processing":
            return {"status": "already_processing"}
        if has_human_work(db, recording_id):
            raise HTTPException(
                status_code=409,
                detail=(
                    "This recording contains human edits or review decisions. Reprocessing is blocked to preserve all drafts and audit history. Import a separate copy to compare a new transcription."
                ),
            )
        db.execute(
            """
            UPDATE recordings
            SET status = 'processing', processing_stage = 'Queued for local processing',
                processed_percent = 1, error = NULL, updated_at = ?
            WHERE id = ?
            """,
            (utc_now(), recording_id),
        )
        metadata = json.loads(db.execute("SELECT metadata_json FROM recordings WHERE id = ?", (recording_id,)).fetchone()[0])
        metadata.update(payload.model_dump())
        db.execute("UPDATE recordings SET metadata_json = ? WHERE id = ?", (json.dumps(metadata), recording_id))
    background_tasks.add_task(
        process_recording,
        recording_id,
        model=payload.model,
        language=payload.language,
        dual_pass=payload.dual_pass,
    )
    return {"status": "processing"}


@app.get("/api/recordings/{recording_id}")
def get_recording(recording_id: str) -> dict[str, Any]:
    with connection() as db:
        recording = row_to_dict(db.execute("SELECT * FROM recordings WHERE id = ?", (recording_id,)).fetchone())
        if not recording:
            raise not_found("Recording")
        counts = dict(
            db.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN status = 'verified' THEN 1 ELSE 0 END) AS verified,
                       SUM(CASE WHEN status IN ('flagged', 'unclear') THEN 1 ELSE 0 END) AS flagged
                FROM cues WHERE recording_id = ?
                """,
                (recording_id,),
            ).fetchone()
        )
        speakers = [
            row["speaker"]
            for row in db.execute(
                "SELECT DISTINCT speaker FROM cues WHERE recording_id = ? ORDER BY speaker", (recording_id,)
            ).fetchall()
        ]
    recording["counts"] = {key: value or 0 for key, value in counts.items()}
    recording["speakers"] = speakers
    return recording


@app.get("/api/recordings/{recording_id}/cues")
def list_cues(
    recording_id: str,
    status: str | None = Query(default=None),
    reason: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    conditions = ["recording_id = ?"]
    values: list[Any] = [recording_id]
    if status:
        conditions.append("status = ?")
        values.append(status)
    if reason:
        conditions.append("ambiguity_reasons LIKE ?")
        values.append(f'%"{reason}"%')
    with connection() as db:
        cues = rows_to_dicts(
            db.execute(
                f"SELECT * FROM cues WHERE {' AND '.join(conditions)} ORDER BY cue_index", values
            ).fetchall()
        )
    for cue in cues:
        cue["diff_source_a"] = word_diff(cue["source_text"], cue["stt_a_text"])
        cue["diff_source_b"] = word_diff(cue["source_text"], cue["stt_b_text"])
    return cues


@app.patch("/api/cues/{cue_id}")
def update_cue(cue_id: int, payload: CueUpdate) -> dict[str, Any]:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        before_row = db.execute("SELECT * FROM cues WHERE id = ?", (cue_id,)).fetchone()
        before = row_to_dict(before_row)
        if not before:
            raise not_found("Cue")
        if payload.expected_revision is not None and payload.expected_revision != before["revision"]:
            raise HTTPException(status_code=409, detail="This cue was changed in another window. Copy your draft, reload the recording, and compare before saving again.")
        if db.execute("SELECT status FROM recordings WHERE id = ?", (before["recording_id"],)).fetchone()[0] == "processing":
            raise HTTPException(status_code=409, detail="Wait for local processing to finish before editing this recording.")
        changes = payload.model_dump(exclude_none=True)
        changes.pop("expected_revision", None)
        reviewer = str(changes.pop("reviewer", "") or "").strip() or "Not recorded"
        if "speaker" in changes:
            changes["speaker"] = str(changes["speaker"]).strip() or "Unknown speaker"
        if "final_text" in changes:
            changes["final_text"] = str(changes["final_text"]).strip()
        if not changes:
            return before
        start_ms = int(changes.get("start_ms", before["start_ms"]))
        end_ms = int(changes.get("end_ms", before["end_ms"]))
        if end_ms <= start_ms:
            raise HTTPException(status_code=422, detail="Cue end time must be after its start time.")
        recording_duration = db.execute(
            "SELECT duration_ms FROM recordings WHERE id = ?", (before["recording_id"],)
        ).fetchone()[0]
        if recording_duration and end_ms > int(recording_duration) + 1_000:
            raise HTTPException(status_code=422, detail="Cue end time cannot extend beyond the recording.")
        resulting_text = str(changes.get("final_text", before["final_text"])).strip()
        if changes.get("status", before["status"]) == "verified" and not resulting_text:
            raise HTTPException(status_code=422, detail="A verified cue must contain transcript text.")
        fields = [f"{key} = ?" for key in changes]
        now = utc_now()
        db.execute(
            f"UPDATE cues SET {', '.join(fields)}, revision = revision + 1, updated_at = ? WHERE id = ?",
            [*changes.values(), now, cue_id],
        )
        after = row_to_dict(db.execute("SELECT * FROM cues WHERE id = ?", (cue_id,)).fetchone())
        db.execute(
            "INSERT INTO audit_log (cue_id, action, before_json, after_json, created_at, reviewer) VALUES (?, ?, ?, ?, ?, ?)",
            (cue_id, "update", json.dumps(before), json.dumps(after), now, reviewer),
        )
    return after or {}


@app.post("/api/cues/{cue_id}/split")
def split_cue(cue_id: int, payload: SplitRequest) -> list[dict[str, Any]]:
    def split_text(value: Any, ratio: float) -> tuple[str, str]:
        text = str(value or "").strip()
        if not text:
            return "", ""
        target = max(1, min(len(text) - 1, round(len(text) * ratio)))
        candidates = [index for index, character in enumerate(text) if character.isspace()]
        if not candidates:
            return (text, "") if ratio >= 0.5 else ("", text)
        split_at = min(candidates, key=lambda index: abs(index - target))
        return text[:split_at].strip(), text[split_at:].strip()

    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM cues WHERE id = ?", (cue_id,)).fetchone()
        cue = row_to_dict(row)
        if not cue:
            raise not_found("Cue")
        if payload.expected_revision is not None and payload.expected_revision != cue["revision"]:
            raise HTTPException(status_code=409, detail="This cue was changed in another window. Copy your draft and reload before splitting.")
        if db.execute("SELECT status FROM recordings WHERE id = ?", (cue["recording_id"],)).fetchone()[0] == "processing":
            raise HTTPException(status_code=409, detail="Wait for local processing to finish before splitting this recording.")
        start_ms = int(payload.start_ms if payload.start_ms is not None else cue["start_ms"])
        end_ms = int(payload.end_ms if payload.end_ms is not None else cue["end_ms"])
        if end_ms <= start_ms:
            raise HTTPException(status_code=422, detail="Cue end time must be after its start time.")
        recording_duration = db.execute(
            "SELECT duration_ms FROM recordings WHERE id = ?", (cue["recording_id"],)
        ).fetchone()[0]
        if recording_duration and end_ms > int(recording_duration) + 1_000:
            raise HTTPException(status_code=422, detail="Cue end time cannot extend beyond the recording.")
        if not start_ms + 120 <= payload.split_ms <= end_ms - 120:
            raise HTTPException(status_code=422, detail="Split point must leave at least 120 ms on each side.")
        ratio = (payload.split_ms - start_ms) / max(1, end_ms - start_ms)
        current_text = payload.final_text if payload.final_text is not None else cue["final_text"]
        speaker = str(payload.speaker if payload.speaker is not None else cue["speaker"]).strip() or "Unknown speaker"
        left_text, right_text = split_text(current_text, ratio)
        left_source, right_source = split_text(cue["source_text"], ratio)
        left_a, right_a = split_text(cue["stt_a_text"], ratio)
        left_b, right_b = split_text(cue["stt_b_text"], ratio)
        now = utc_now()
        # Move affected indexes out of the unique-key range before shifting them back.
        # A direct +1 update can collide with the next cue while SQLite visits rows.
        db.execute(
            "UPDATE cues SET cue_index = cue_index + 1000000 WHERE recording_id = ? AND cue_index > ?",
            (cue["recording_id"], cue["cue_index"]),
        )
        db.execute(
            "UPDATE cues SET cue_index = cue_index - 999999 WHERE recording_id = ? AND cue_index > 1000000",
            (cue["recording_id"],),
        )
        db.execute(
            """
            UPDATE cues
            SET start_ms = ?, end_ms = ?, source_text = ?, stt_a_text = ?, stt_b_text = ?,
                final_text = ?, speaker = ?, status = 'pending', revision = revision + 1, updated_at = ?
            WHERE id = ?
            """,
            (start_ms, payload.split_ms, left_source, left_a, left_b, left_text, speaker, now, cue_id),
        )
        db.execute(
            """
            INSERT INTO cues (
                recording_id, cue_index, start_ms, end_ms, source_text, stt_a_text, stt_b_text,
                final_text, speaker, confidence_a, confidence_b, ambiguity_score,
                ambiguity_reasons, status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                cue["recording_id"],
                cue["cue_index"] + 1,
                payload.split_ms,
                end_ms,
                right_source,
                right_a,
                right_b,
                right_text,
                speaker,
                cue["confidence_a"],
                cue["confidence_b"],
                cue["ambiguity_score"],
                json.dumps(cue["ambiguity_reasons"]),
                now,
            ),
        )
        split_after = rows_to_dicts(
            db.execute(
                "SELECT * FROM cues WHERE recording_id = ? AND cue_index IN (?, ?) ORDER BY cue_index",
                (cue["recording_id"], cue["cue_index"], cue["cue_index"] + 1),
            ).fetchall()
        )
        db.execute(
            "INSERT INTO audit_log (cue_id, action, before_json, after_json, created_at, reviewer) VALUES (?, ?, ?, ?, ?, ?)",
            (cue_id, "split", json.dumps(cue), json.dumps(split_after), now, (payload.reviewer or "").strip() or "Not recorded"),
        )
        result = rows_to_dicts(
            db.execute(
                "SELECT * FROM cues WHERE recording_id = ? ORDER BY cue_index", (cue["recording_id"],)
            ).fetchall()
        )
    return result


@app.get("/api/cues/{cue_id}/history")
def cue_history(cue_id: int) -> list[dict[str, Any]]:
    with connection() as db:
        rows = db.execute("SELECT * FROM audit_log WHERE cue_id = ? ORDER BY id DESC", (cue_id,)).fetchall()
    output = []
    for row in rows:
        item = dict(row)
        item["before"] = json.loads(item.pop("before_json"))
        item["after"] = json.loads(item.pop("after_json"))
        output.append(item)
    return output


@app.get("/api/recordings/{recording_id}/media")
def recording_media(recording_id: str) -> FileResponse:
    with connection() as db:
        row = db.execute("SELECT media_path FROM recordings WHERE id = ?", (recording_id,)).fetchone()
    if not row:
        raise not_found("Media")
    media_path = managed_file(row["media_path"])
    if not media_path.exists():
        raise not_found("Media")
    media_type, _ = mimetypes.guess_type(media_path.name)
    return FileResponse(
        media_path,
        media_type=media_type or "application/octet-stream",
        headers={"Content-Disposition": content_disposition(media_path.name, "inline")},
    )


def recording_and_cues(recording_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with connection() as db:
        recording = row_to_dict(db.execute("SELECT * FROM recordings WHERE id = ?", (recording_id,)).fetchone())
        if not recording:
            raise not_found("Recording")
        cues = rows_to_dicts(db.execute("SELECT * FROM cues WHERE recording_id = ? ORDER BY cue_index", (recording_id,)).fetchall())
    return recording, cues


def recording_audit(recording_id: str) -> list[dict[str, Any]]:
    with connection() as db:
        return rows_to_dicts(
            db.execute(
                """
                SELECT a.* FROM audit_log a JOIN cues c ON c.id = a.cue_id
                WHERE c.recording_id = ? ORDER BY a.id
                """,
                (recording_id,),
            ).fetchall()
        )


def export_bytes(format_name: str, cues: list[dict[str, Any]]) -> tuple[bytes, str]:
    def spreadsheet_safe(value: Any) -> Any:
        if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
            return "'" + value
        return value

    if format_name == "vtt":
        return to_vtt(cues).encode("utf-8"), "text/vtt; charset=utf-8"
    if format_name == "srt":
        return to_srt(cues).encode("utf-8"), "application/x-subrip; charset=utf-8"
    if format_name == "json":
        return json.dumps(cues, ensure_ascii=False, indent=2).encode("utf-8"), "application/json"
    if format_name == "csv":
        output = io.StringIO()
        fieldnames = [
            "cue_index", "start", "end", "speaker", "source_text", "stt_a_text", "stt_b_text",
            "final_text", "status", "ambiguity_score", "ambiguity_reasons",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for cue in cues:
            writer.writerow(
                {key: spreadsheet_safe(value) for key, value in {
                    "cue_index": cue["cue_index"],
                    "start": format_timestamp(cue["start_ms"]),
                    "end": format_timestamp(cue["end_ms"]),
                    "speaker": cue["speaker"],
                    "source_text": cue["source_text"],
                    "stt_a_text": cue["stt_a_text"],
                    "stt_b_text": cue["stt_b_text"],
                    "final_text": cue["final_text"],
                    "status": cue["status"],
                    "ambiguity_score": cue["ambiguity_score"],
                    "ambiguity_reasons": ";".join(cue["ambiguity_reasons"]),
                }.items()}
            )
        return output.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8"
    if format_name == "changes":
        output = io.StringIO()
        fieldnames = [
            "cue_index", "start", "end", "speaker", "before_source_vtt", "after_current_text",
            "changed", "stt_a", "stt_b", "status", "ambiguity_score", "ambiguity_reasons",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for cue in cues:
            before = str(cue["source_text"]).strip()
            after = str(cue["final_text"]).strip()
            writer.writerow(
                {key: spreadsheet_safe(value) for key, value in {
                    "cue_index": cue["cue_index"],
                    "start": format_timestamp(cue["start_ms"]),
                    "end": format_timestamp(cue["end_ms"]),
                    "speaker": cue["speaker"],
                    "before_source_vtt": before,
                    "after_current_text": after,
                    "changed": "Yes" if before != after else "No",
                    "stt_a": cue["stt_a_text"],
                    "stt_b": cue["stt_b_text"],
                    "status": cue["status"],
                    "ambiguity_score": cue["ambiguity_score"],
                    "ambiguity_reasons": ";".join(cue["ambiguity_reasons"]),
                }.items()}
            )
        return output.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8"
    if format_name == "report":
        changed = [cue for cue in cues if str(cue["source_text"]).strip() != str(cue["final_text"]).strip()]
        unresolved = [cue for cue in cues if cue["status"] != "verified"]
        lines = [
            "# Transcript Change Report",
            "",
            f"- Total cues: {len(cues)}",
            f"- Text changes from Source VTT: {len(changed)}",
            f"- Human-verified cues: {len(cues) - len(unresolved)}",
            f"- Unresolved or unclear cues: {len(unresolved)}",
            "",
            "## Before/after list",
            "",
        ]
        if not changed:
            lines.append("No verified wording changes have been made from the Source VTT.")
        for cue in changed:
            reasons = ", ".join(reason.replace("_", " ") for reason in cue["ambiguity_reasons"]) or "manual review"
            lines.extend(
                [
                    f"### Cue {cue['cue_index']} · {format_timestamp(cue['start_ms'])}–{format_timestamp(cue['end_ms'])}",
                    "",
                    f"- Speaker: {cue['speaker']}",
                    f"- Before (Source VTT): {cue['source_text']}",
                    f"- After ({'Verified' if cue['status'] == 'verified' else 'Current draft'}): {cue['final_text']}",
                    f"- Review evidence: STT A — {cue['stt_a_text'] or '[no aligned text]'}; STT B — {cue['stt_b_text'] or '[no aligned text]'}",
                    f"- Flag reason: {reasons}",
                    "",
                ]
            )
        return "\n".join(lines).encode("utf-8"), "text/markdown; charset=utf-8"
    raise HTTPException(status_code=404, detail="Unsupported export format")


@app.get("/api/recordings/{recording_id}/export/{format_name}")
def export_recording(
    recording_id: str,
    format_name: Literal["vtt", "srt", "csv", "json", "changes", "report", "docx", "nvivo", "xlsx", "txt"],
) -> Response:
    recording, cues = recording_and_cues(recording_id)
    if not cues:
        raise HTTPException(status_code=409, detail="No transcript segments are available to export yet.")
    if format_name in {"docx", "nvivo", "xlsx", "txt"}:
        content, media_type, filename = export_docx_bundle(format_name, recording, cues, recording_audit(recording_id))
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": content_disposition(filename)},
        )
    if format_name == "changes":
        content, media_type = csv_bytes(change_rows(recording, cues, recording_audit(recording_id)), CHANGE_FIELDS), "text/csv; charset=utf-8"
    elif format_name == "report":
        content, media_type = change_report_bytes(recording, cues, recording_audit(recording_id)), "text/markdown; charset=utf-8"
    else:
        content, media_type = export_bytes(format_name, cues)
    if format_name == "changes":
        filename = f"{safe_filename(recording['name'])}-change-list.csv"
    elif format_name == "report":
        filename = f"{safe_filename(recording['name'])}-change-report.md"
    else:
        filename = f"{safe_filename(recording['name'])}-{transcript_state(cues)}.{format_name}"
    return Response(content=content, media_type=media_type, headers={"Content-Disposition": content_disposition(filename)})


def _delete_temporary_export(path: Path) -> None:
    path.unlink(missing_ok=True)


@app.get("/api/projects/{project_id}/bundle")
def export_project_bundle(project_id: str, include_media: bool = Query(default=False)) -> FileResponse:
    project = fetch_project(project_id)
    if not project:
        raise not_found("Project")
    payloads = []
    for recording_summary in project["recordings"]:
        recording, cues = recording_and_cues(recording_summary["id"])
        recording["media_path"] = str(managed_file(recording["media_path"]))
        if recording.get("source_path"):
            recording["source_path"] = str(managed_file(recording["source_path"]))
        payloads.append({"recording": recording, "cues": cues, "audit": recording_audit(recording["id"])})
    if not any(payload["cues"] for payload in payloads):
        raise HTTPException(status_code=409, detail="No transcript segments are available to export yet.")

    with tempfile.NamedTemporaryFile(prefix="trs-qualitative-", suffix=".zip", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with temporary_path.open("w+b") as output:
            write_project_package(output, project, payloads, include_media=include_media)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    privacy_suffix = "restricted_with_media" if include_media else "analysis"
    filename = f"{research_slug(project['name'])}_qualitative_{privacy_suffix}_package_v{PACKAGE_VERSION.replace('.', '_')}.zip"
    return FileResponse(
        temporary_path,
        media_type="application/zip",
        headers={"Content-Disposition": content_disposition(filename)},
        background=BackgroundTask(_delete_temporary_export, temporary_path),
    )
