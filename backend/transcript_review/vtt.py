from __future__ import annotations

import html
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass

TIMING_RE = re.compile(
    r"(?P<start>(?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3})\s*-->\s*"
    r"(?P<end>(?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3})(?:\s+.*)?$"
)
TAG_RE = re.compile(r"<[^>]+>")
VOICE_RE = re.compile(r"^<v(?:\.[^ >]+)*\s+([^>]+)>", re.IGNORECASE)
SPEAKER_PREFIX_RE = re.compile(
    r"^(?P<speaker>(?:Researcher|Moderator|Interviewer|Facilitator|Participant(?:\s+\d+)?|Unknown speaker|P\d{1,4}))\s*:\s*(?P<text>.+)$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class Cue:
    start_ms: int
    end_ms: int
    text: str
    speaker: str = "Unknown speaker"

    def as_dict(self) -> dict:
        return asdict(self)


def parse_timestamp(value: str) -> int:
    normalized = value.replace(",", ".")
    parts = normalized.split(":")
    if len(parts) == 2:
        hours = 0
        minutes, seconds = parts
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        raise ValueError(f"Invalid subtitle timestamp: {value}")
    second_value, millis = seconds.split(".")
    if not (0 <= int(minutes) < 60 and 0 <= int(second_value) < 60 and len(millis) == 3):
        raise ValueError(f"Invalid subtitle timestamp: {value}")
    return ((int(hours) * 60 + int(minutes)) * 60 + int(second_value)) * 1000 + int(millis)


def format_timestamp(milliseconds: int, separator: str = ".") -> str:
    milliseconds = max(0, int(milliseconds))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{millis:03d}"


def clean_text(value: str) -> tuple[str, str]:
    speaker_match = VOICE_RE.match(value.strip())
    speaker = html.unescape(speaker_match.group(1)).strip() if speaker_match else "Unknown speaker"
    text = TAG_RE.sub("", value)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", " ", text).strip()
    if speaker == "Unknown speaker":
        inferred_speaker, inferred_text = infer_speaker_prefix(text)
        if inferred_speaker:
            speaker, text = inferred_speaker, inferred_text
    return text, speaker


def infer_speaker_prefix(text: str) -> tuple[str | None, str]:
    match = SPEAKER_PREFIX_RE.match(text.strip())
    if not match:
        return None, text
    speaker = match.group("speaker").strip()
    if speaker.casefold().startswith("p") and speaker[1:].isdigit():
        speaker = speaker.upper()
    else:
        speaker = speaker[:1].upper() + speaker[1:]
    return speaker, match.group("text").strip()


def parse_vtt(content: str) -> list[Cue]:
    normalized = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", normalized)
    cues: list[Cue] = []
    for block in blocks:
        lines = [line.strip("\ufeff") for line in block.splitlines()]
        if not lines or lines[0].strip().upper().startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue
        timing_index = next((index for index, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        match = TIMING_RE.search(lines[timing_index].strip())
        if not match:
            raise ValueError(f"Invalid caption timing: {lines[timing_index].strip()}")
        if parse_timestamp(match.group("end")) <= parse_timestamp(match.group("start")):
            raise ValueError("Each caption must end after it starts.")
        raw_text = "\n".join(lines[timing_index + 1 :]).strip()
        text, speaker = clean_text(raw_text)
        if not text:
            continue
        cues.append(
            Cue(
                start_ms=parse_timestamp(match.group("start")),
                end_ms=parse_timestamp(match.group("end")),
                text=text,
                speaker=speaker,
            )
        )
    return cues


def cue_text(cue: dict) -> str:
    text = str(cue.get("final_text", cue.get("source_text") or cue.get("stt_a_text") or "")).strip()
    speaker = str(cue.get("speaker") or "Unknown speaker").strip()
    if speaker and speaker != "Unknown speaker":
        return f"<v {html.escape(speaker)}>{html.escape(text)}"
    return html.escape(text)


def to_vtt(cues: Iterable[dict]) -> str:
    blocks = ["WEBVTT"]
    for index, cue in enumerate(cues, start=1):
        blocks.append(
            f"{index}\n{format_timestamp(cue['start_ms'])} --> {format_timestamp(cue['end_ms'])}\n{cue_text(cue)}"
        )
    return "\n\n".join(blocks) + "\n"


def to_srt(cues: Iterable[dict]) -> str:
    blocks: list[str] = []
    for index, cue in enumerate(cues, start=1):
        text = str(cue.get("final_text", cue.get("source_text") or cue.get("stt_a_text") or "")).strip()
        speaker = str(cue.get("speaker") or "Unknown speaker").strip()
        if speaker and speaker != "Unknown speaker":
            text = f"{speaker}: {text}"
        blocks.append(
            f"{index}\n{format_timestamp(cue['start_ms'], ',')} --> {format_timestamp(cue['end_ms'], ',')}\n{text}"
        )
    return "\n\n".join(blocks) + "\n"
