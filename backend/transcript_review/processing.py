from __future__ import annotations

import json
import math
import platform
import re
import shutil
import subprocess
import traceback
from functools import wraps
from pathlib import Path
from threading import Lock
from typing import Any

from .compare import create_aligned_cues, overlap_ms
from .database import connection, has_human_work, utc_now
from .vtt import parse_vtt

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
SILENCE_RE = re.compile(r"silence_(start|end):\s*([0-9.]+)")
PROCESSING_LOCK = Lock()


def serialized_processing(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with PROCESSING_LOCK:
            return function(*args, **kwargs)

    return wrapped


def require_executable(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"{name} is required but was not found on this computer.")
    return path


def probe_media(path: Path) -> dict[str, Any]:
    ffprobe = require_executable("ffprobe")
    command = [
        ffprobe,
        "-v",
        "error",
        "-protocol_whitelist",
        "file,pipe",
        "-show_entries",
        "format=duration:stream=index,codec_type,codec_name,width,height",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=60)
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    duration_seconds = float(payload.get("format", {}).get("duration") or 0)
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if not audio_stream or not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError("Choose a finite-duration recording with an audio stream.")
    return {
        "duration_ms": round(duration_seconds * 1000),
        "media_type": "video" if video_stream else "audio",
        "video_codec": video_stream.get("codec_name") if video_stream else None,
        "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
        "width": video_stream.get("width") if video_stream else None,
        "height": video_stream.get("height") if video_stream else None,
    }


def normalize_audio(media_path: Path, output_path: Path) -> Path:
    ffmpeg = require_executable("ffmpeg")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-v",
        "error",
        "-protocol_whitelist",
        "file,pipe",
        "-i",
        str(media_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]
    subprocess.run(command, capture_output=True, text=True, check=True)
    return output_path


def detect_speech_regions(path: Path, duration_ms: int) -> list[tuple[int, int]]:
    ffmpeg = require_executable("ffmpeg")
    command = [
        ffmpeg,
        "-hide_banner",
        "-nostats",
        "-protocol_whitelist",
        "file,pipe",
        "-i",
        str(path),
        "-af",
        "silencedetect=noise=-38dB:d=0.35",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return [(0, duration_ms)]
    silences: list[tuple[int, int]] = []
    current_start: int | None = None
    for kind, seconds in SILENCE_RE.findall(result.stderr):
        value = round(float(seconds) * 1000)
        if kind == "start":
            current_start = value
        elif current_start is not None:
            silences.append((current_start, value))
            current_start = None
    if current_start is not None:
        silences.append((current_start, duration_ms))
    speech: list[tuple[int, int]] = []
    cursor = 0
    for silence_start, silence_end in silences:
        if silence_start > cursor + 80:
            speech.append((cursor, silence_start))
        cursor = max(cursor, silence_end)
    if cursor < duration_ms - 80:
        speech.append((cursor, duration_ms))
    return speech or [(0, duration_ms)]


def _segment_confidence(segment: dict[str, Any]) -> float | None:
    if segment.get("avg_logprob") is None:
        return None
    return round(max(0.0, min(1.0, math.exp(float(segment["avg_logprob"])))), 4)


def run_mlx_whisper(
    audio_path: Path,
    *,
    model: str,
    condition_on_previous_text: bool,
    language: str | None,
) -> list[dict[str, Any]]:
    try:
        import mlx_whisper
    except ImportError as exc:
        raise RuntimeError(
            "MLX Whisper is not installed. Install mlx-whisper on Apple Silicon or configure another STT provider."
        ) from exc
    options: dict[str, Any] = {
        "path_or_hf_repo": model,
        "verbose": False,
        "word_timestamps": True,
        "condition_on_previous_text": condition_on_previous_text,
        "temperature": 0.0 if condition_on_previous_text else (0.0, 0.2),
    }
    if language and language != "auto":
        options["language"] = language
    result = mlx_whisper.transcribe(str(audio_path), **options)
    return [
        {
            "start_ms": round(float(segment.get("start", 0)) * 1000),
            "end_ms": round(float(segment.get("end", 0)) * 1000),
            "text": str(segment.get("text", "")).strip(),
            "confidence": _segment_confidence(segment),
            "words": segment.get("words", []),
        }
        for segment in result.get("segments", [])
        if str(segment.get("text", "")).strip()
    ]


def run_faster_whisper(
    audio_path: Path,
    *,
    model: str,
    condition_on_previous_text: bool,
    language: str | None,
) -> list[dict[str, Any]]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "No supported local STT engine is installed. Apple Silicon uses mlx-whisper; other systems can install faster-whisper."
        ) from exc
    model_name = model.split("/")[-1]
    model_name = model_name.removeprefix("whisper-").removesuffix("-mlx")
    if model_name == "large-v3-turbo":
        model_name = "turbo"
    whisper = WhisperModel(model_name, device="auto", compute_type="auto")
    segments, _ = whisper.transcribe(
        str(audio_path),
        language=None if not language or language == "auto" else language,
        word_timestamps=True,
        condition_on_previous_text=condition_on_previous_text,
        temperature=0.0,
    )
    output: list[dict[str, Any]] = []
    for segment in segments:
        text = str(segment.text).strip()
        if not text:
            continue
        output.append(
            {
                "start_ms": round(float(segment.start) * 1000),
                "end_ms": round(float(segment.end) * 1000),
                "text": text,
                "confidence": round(max(0.0, min(1.0, math.exp(float(segment.avg_logprob)))), 4),
                "words": [
                    {
                        "start": word.start,
                        "end": word.end,
                        "word": word.word,
                        "probability": word.probability,
                    }
                    for word in (segment.words or [])
                ],
            }
        )
    return output


def run_local_stt(
    audio_path: Path,
    *,
    model: str,
    condition_on_previous_text: bool,
    language: str | None,
) -> list[dict[str, Any]]:
    try:
        import mlx_whisper  # noqa: F401

        mlx_available = platform.system() == "Darwin" and platform.machine() == "arm64"
    except ImportError:
        mlx_available = False
    if mlx_available:
        return run_mlx_whisper(
            audio_path,
            model=model,
            condition_on_previous_text=condition_on_previous_text,
            language=language,
        )
    return run_faster_whisper(
        audio_path,
        model=model,
        condition_on_previous_text=condition_on_previous_text,
        language=language,
    )


def assign_named_speakers(
    cues: list[dict[str, Any]],
    track_regions: dict[str, list[tuple[int, int]]],
) -> None:
    for cue in cues:
        scores: dict[str, int] = {}
        for speaker, regions in track_regions.items():
            scores[speaker] = sum(
                overlap_ms(cue["start_ms"], cue["end_ms"], region_start, region_end)
                for region_start, region_end in regions
            )
        if scores:
            ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
            top_speaker, top_overlap = ranked[0]
            next_overlap = ranked[1][1] if len(ranked) > 1 else 0
            cue_duration = max(1, cue["end_ms"] - cue["start_ms"])
            if top_overlap >= min(280, cue_duration * 0.22) and top_overlap > next_overlap * 1.08:
                cue["speaker"] = top_speaker
            elif top_overlap > 0 and top_overlap == next_overlap:
                if "speaker_mismatch" not in cue["ambiguity_reasons"]:
                    cue["ambiguity_reasons"].append("speaker_mismatch")
                cue["ambiguity_score"] = min(100, cue["ambiguity_score"] + 12)
                cue["status"] = "flagged"


def update_recording(recording_id: str, *, stage: str, percent: int, status: str | None = None, error: str | None = None) -> None:
    fields = ["processing_stage = ?", "processed_percent = ?", "updated_at = ?"]
    values: list[Any] = [stage, percent, utc_now()]
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if error is not None:
        fields.append("error = ?")
        values.append(error)
    values.append(recording_id)
    with connection() as db:
        db.execute(f"UPDATE recordings SET {', '.join(fields)} WHERE id = ?", values)


@serialized_processing
def process_recording(
    recording_id: str,
    *,
    model: str = DEFAULT_MODEL,
    language: str | None = "auto",
    dual_pass: bool = True,
) -> None:
    try:
        with connection() as db:
            recording = db.execute("SELECT * FROM recordings WHERE id = ?", (recording_id,)).fetchone()
            tracks = db.execute(
                "SELECT speaker, path FROM speaker_tracks WHERE recording_id = ? ORDER BY id", (recording_id,)
            ).fetchall()
        if not recording:
            return
        media_path = Path(recording["media_path"])
        work_dir = media_path.parent / "processing"
        audio_path = work_dir / "audio-16k.wav"

        update_recording(recording_id, stage="Inspecting local media", percent=4, status="processing", error="")
        media_info = probe_media(media_path)
        update_recording(recording_id, stage="Extracting speech audio", percent=10)
        normalize_audio(media_path, audio_path)
        vad_regions = detect_speech_regions(audio_path, media_info["duration_ms"])

        source: list[dict[str, Any]] = []
        if recording["source_path"]:
            source = [cue.as_dict() for cue in parse_vtt(Path(recording["source_path"]).read_text(encoding="utf-8-sig"))]

        update_recording(recording_id, stage="Running local STT pass A", percent=18)
        pass_a = run_local_stt(
            audio_path,
            model=model,
            condition_on_previous_text=True,
            language=language,
        )
        pass_b: list[dict[str, Any]] = []
        if dual_pass:
            update_recording(recording_id, stage="Running alternate-context STT pass B", percent=58)
            pass_b = run_local_stt(
                audio_path,
                model=model,
                condition_on_previous_text=False,
                language=language,
            )

        update_recording(recording_id, stage="Aligning transcript versions", percent=88)
        aligned = create_aligned_cues(source, pass_a, pass_b)

        track_regions: dict[str, list[tuple[int, int]]] = {}
        if tracks:
            update_recording(recording_id, stage="Assigning named speaker tracks", percent=93)
            for track in tracks:
                track_path = Path(track["path"])
                track_info = probe_media(track_path)
                track_regions[track["speaker"]] = detect_speech_regions(track_path, track_info["duration_ms"])
            assign_named_speakers(aligned, track_regions)

        metadata = {
            **media_info,
            "model": model,
            "language": language,
            "dual_pass": dual_pass,
            "vad_region_count": len(vad_regions),
            "named_speaker_tracks": list(track_regions),
            "processing_is_local": True,
        }
        now = utc_now()
        with connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if has_human_work(db, recording_id):
                raise RuntimeError("Human edits were found. Existing cues and audit history were preserved; import a separate copy to reprocess.")
            db.execute("DELETE FROM cues WHERE recording_id = ?", (recording_id,))
            db.executemany(
                """
                INSERT INTO cues (
                    recording_id, cue_index, start_ms, end_ms, source_text, stt_a_text, stt_b_text,
                    final_text, speaker, confidence_a, confidence_b, ambiguity_score,
                    ambiguity_reasons, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        recording_id,
                        cue["cue_index"],
                        cue["start_ms"],
                        cue["end_ms"],
                        cue["source_text"],
                        cue["stt_a_text"],
                        cue["stt_b_text"],
                        cue["final_text"],
                        cue["speaker"],
                        cue["confidence_a"],
                        cue["confidence_b"],
                        cue["ambiguity_score"],
                        json.dumps(cue["ambiguity_reasons"]),
                        cue["status"],
                        now,
                    )
                    for cue in aligned
                ],
            )
            db.execute(
                """
                UPDATE recordings
                SET duration_ms = ?, status = 'ready', processing_stage = 'Ready for human review',
                    processed_percent = 100, error = NULL, metadata_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (media_info["duration_ms"], json.dumps(metadata), now, recording_id),
            )
    # This is the background-task boundary: every unexpected engine, filesystem,
    # or media failure must become a retryable recording state instead of leaving
    # the job permanently marked as processing.
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        update_recording(
            recording_id,
            stage="Processing failed",
            percent=0,
            status="error",
            error=f"{type(exc).__name__}: {exc}",
        )
