from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

WORD_RE = re.compile(r"[\w’']+|[^\w\s]", re.UNICODE)


def normalize(text: str) -> str:
    words = WORD_RE.findall(text.casefold())
    return " ".join(word for word in words if re.search(r"\w", word))


def similarity(left: str, right: str) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, normalize(left), normalize(right)).ratio()


def overlap_ms(start_a: int, end_a: int, start_b: int, end_b: int) -> int:
    return max(0, min(end_a, end_b) - max(start_a, start_b))


def text_for_window(segments: list[dict[str, Any]], start_ms: int, end_ms: int) -> tuple[str, float | None, int]:
    matches = [
        segment
        for segment in segments
        if overlap_ms(start_ms, end_ms, int(segment["start_ms"]), int(segment["end_ms"])) > 0
    ]
    if not matches:
        return "", None, 0
    timed_words: list[dict[str, Any]] = []
    has_word_timing = False
    for segment in matches:
        for word in segment.get("words") or []:
            if word.get("start") is None or word.get("end") is None:
                continue
            has_word_timing = True
            word_start = round(float(word["start"]) * 1000)
            word_end = round(float(word["end"]) * 1000)
            word_center = (word_start + word_end) // 2
            if start_ms <= word_center < end_ms:
                timed_words.append({**word, "start_ms": word_start, "end_ms": word_end})
    if timed_words:
        # Whisper word tokens normally include their own leading whitespace. Preserve
        # it when possible, then normalize only the outer edge of the cue.
        text = "".join(str(word.get("word", "")) for word in timed_words).strip()
        probabilities = [float(word["probability"]) for word in timed_words if word.get("probability") is not None]
        confidence = sum(probabilities) / len(probabilities) if probabilities else None
        edge_drift = max(abs(timed_words[0]["start_ms"] - start_ms), abs(timed_words[-1]["end_ms"] - end_ms))
        return text, confidence, edge_drift
    if has_word_timing:
        return "", None, 0
    text = " ".join(str(item.get("text", "")).strip() for item in matches).strip()
    confidences = [float(item["confidence"]) for item in matches if item.get("confidence") is not None]
    confidence = sum(confidences) / len(confidences) if confidences else None
    edge_drift = max(abs(int(matches[0]["start_ms"]) - start_ms), abs(int(matches[-1]["end_ms"]) - end_ms))
    return text, confidence, edge_drift


def uncovered_stt_windows(
    source: list[dict[str, Any]], segments: list[dict[str, Any]], *, source_padding_ms: int = 250
) -> list[dict[str, Any]]:
    """Find STT words that fall outside every source-caption window.

    Source VTT cues remain the primary anchors, but they cannot reveal an entire
    omitted sentence. These extra windows make likely omissions visible to the
    human reviewer instead of silently dropping them from the queue.
    """
    if not source or not segments:
        return []
    covered = [
        (max(0, int(cue["start_ms"]) - source_padding_ms), int(cue["end_ms"]) + source_padding_ms)
        for cue in source
    ]
    uncovered_words: list[dict[str, Any]] = []
    fallback_windows: list[dict[str, Any]] = []
    for segment in segments:
        words = [word for word in segment.get("words") or [] if word.get("start") is not None and word.get("end") is not None]
        if words:
            for word in words:
                start_ms = round(float(word["start"]) * 1000)
                end_ms = round(float(word["end"]) * 1000)
                center = (start_ms + end_ms) // 2
                if not any(start <= center < end for start, end in covered):
                    uncovered_words.append({**word, "start_ms": start_ms, "end_ms": end_ms})
            continue
        segment_start = int(segment["start_ms"])
        segment_end = int(segment["end_ms"])
        duration = max(1, segment_end - segment_start)
        overlap = sum(overlap_ms(segment_start, segment_end, start, end) for start, end in covered)
        if overlap < duration * 0.35:
            fallback_windows.append({"start_ms": segment_start, "end_ms": segment_end, "_source_anchor": False})

    windows: list[dict[str, Any]] = []
    for word in sorted(uncovered_words, key=lambda item: (item["start_ms"], item["end_ms"])):
        if windows and word["start_ms"] - windows[-1]["end_ms"] <= 750:
            windows[-1]["end_ms"] = max(windows[-1]["end_ms"], word["end_ms"])
        else:
            windows.append(
                {"start_ms": word["start_ms"], "end_ms": word["end_ms"], "_source_anchor": False}
            )
    return windows + fallback_windows


def create_aligned_cues(
    source: list[dict[str, Any]],
    pass_a: list[dict[str, Any]],
    pass_b: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if source:
        anchors = [{**cue, "_source_anchor": True} for cue in source]
        # Either pass can recover speech omitted by the source captions. Combining
        # their timed words lets one pass rescue an omission missed by the other;
        # overlapping windows are coalesced by ``uncovered_stt_windows``.
        anchors.extend(uncovered_stt_windows(source, [*pass_a, *pass_b]))
        anchors.sort(key=lambda cue: (int(cue["start_ms"]), int(cue["end_ms"])))
    else:
        anchors = pass_a or pass_b
    output: list[dict[str, Any]] = []
    for cue_index, anchor in enumerate(anchors, start=1):
        start_ms = int(anchor["start_ms"])
        end_ms = max(start_ms + 150, int(anchor["end_ms"]))
        source_text = str(anchor.get("text", "")) if source and anchor.get("_source_anchor", False) else ""
        speaker = str(anchor.get("speaker") or "Unknown speaker")
        a_text, confidence_a, drift_a = text_for_window(pass_a, start_ms, end_ms)
        b_text, confidence_b, drift_b = text_for_window(pass_b, start_ms, end_ms)
        if not source and pass_a is anchors:
            a_text = str(anchor.get("text", ""))
            confidence_a = anchor.get("confidence")
        if not source and not pass_a and pass_b is anchors:
            b_text = str(anchor.get("text", ""))
            confidence_b = anchor.get("confidence")

        versions = [text for text in (source_text, a_text, b_text) if text]
        pair_scores = [similarity(versions[i], versions[j]) for i in range(len(versions)) for j in range(i + 1, len(versions))]
        agreement = sum(pair_scores) / len(pair_scores) if pair_scores else 1.0
        reasons: list[str] = []
        if len(versions) >= 2 and agreement < 0.86:
            reasons.append("word_disagreement")
        if any(value is not None and value < 0.62 for value in (confidence_a, confidence_b)):
            reasons.append("low_confidence")
        if max(drift_a, drift_b) > 900:
            reasons.append("timing_drift")
        if (pass_a and not a_text) or (pass_b and not b_text):
            reasons.append("missing_version")
        if source and not source_text:
            reasons.append("missing_source")

        confidence_penalty = max(
            [max(0.0, 0.72 - value) for value in (confidence_a, confidence_b) if value is not None] or [0.0]
        )
        score = round(min(100.0, (1.0 - agreement) * 100.0 + confidence_penalty * 45.0 + len(reasons) * 5.0))
        final_text = source_text or a_text or b_text
        output.append(
            {
                "cue_index": cue_index,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "source_text": source_text,
                "stt_a_text": a_text,
                "stt_b_text": b_text,
                "final_text": final_text,
                "speaker": speaker,
                "confidence_a": confidence_a,
                "confidence_b": confidence_b,
                "ambiguity_score": int(score),
                "ambiguity_reasons": reasons,
                "status": "flagged" if reasons else "pending",
            }
        )
    return output


def word_diff(left: str, right: str) -> list[dict[str, str]]:
    left_words = WORD_RE.findall(left)
    right_words = WORD_RE.findall(right)
    matcher = SequenceMatcher(None, [word.casefold() for word in left_words], [word.casefold() for word in right_words])
    result: list[dict[str, str]] = []
    for opcode, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if opcode == "equal":
            result.append({"kind": "equal", "text": " ".join(right_words[right_start:right_end])})
        elif opcode in {"replace", "insert"}:
            result.append({"kind": "changed", "text": " ".join(right_words[right_start:right_end])})
        elif opcode == "delete":
            result.append({"kind": "removed", "text": " ".join(left_words[left_start:left_end])})
    return [item for item in result if item["text"]]
