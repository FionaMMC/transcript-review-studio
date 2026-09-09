from __future__ import annotations

import argparse
import json
import sqlite3
import uuid

from transcript_review.compare import similarity
from transcript_review.database import DATA_DIR, connection, utc_now
from transcript_review.vtt import infer_speaker_prefix


def rescore(source: str, pass_a: str, pass_b: str, confidence_a: float | None, confidence_b: float | None, existing: list[str]) -> tuple[int, list[str]]:
    versions = [text for text in (source, pass_a, pass_b) if text]
    pair_scores = [similarity(versions[i], versions[j]) for i in range(len(versions)) for j in range(i + 1, len(versions))]
    agreement = sum(pair_scores) / len(pair_scores) if pair_scores else 1.0
    reasons = [reason for reason in existing if reason not in {"word_disagreement", "low_confidence"}]
    if len(versions) >= 2 and agreement < 0.86:
        reasons.append("word_disagreement")
    if any(value is not None and value < 0.62 for value in (confidence_a, confidence_b)):
        reasons.append("low_confidence")
    confidence_penalty = max(
        [max(0.0, 0.72 - value) for value in (confidence_a, confidence_b) if value is not None] or [0.0]
    )
    score = round(min(100.0, (1.0 - agreement) * 100.0 + confidence_penalty * 45.0 + len(reasons) * 5.0))
    return int(score), reasons


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview a legacy speaker-prefix migration. Close Studio and back up research data first.")
    parser.add_argument("--apply", action="store_true", help="Apply only to untouched machine cues, with a backup and audit entries")
    args = parser.parse_args()
    changed = 0
    with connection() as db:
        if args.apply:
            backup_path = DATA_DIR / f"studio-before-speaker-migration-{uuid.uuid4().hex}.sqlite3"
            with sqlite3.connect(backup_path) as backup:
                db.backup(backup)
            backup_path.chmod(0o600)
        db.execute("BEGIN IMMEDIATE")
        rows = db.execute("""SELECT c.* FROM cues c JOIN recordings r ON r.id = c.recording_id
            WHERE c.status IN ('pending', 'flagged') AND r.status != 'processing'
            AND NOT EXISTS (SELECT 1 FROM audit_log a WHERE a.cue_id = c.id)""").fetchall()
        for row in rows:
            speaker, clean_source = infer_speaker_prefix(row["source_text"])
            if not speaker:
                continue
            changed += 1
            if not args.apply:
                continue
            final_text = clean_source if row["final_text"].strip() == row["source_text"].strip() else row["final_text"]
            existing_reasons = json.loads(row["ambiguity_reasons"])
            score, reasons = rescore(
                clean_source,
                row["stt_a_text"],
                row["stt_b_text"],
                row["confidence_a"],
                row["confidence_b"],
                existing_reasons,
            )
            status = "flagged" if reasons else "pending"
            db.execute(
                """
                UPDATE cues SET source_text = ?, final_text = ?, speaker = ?, ambiguity_score = ?,
                    ambiguity_reasons = ?, status = ?, revision = revision + 1, updated_at = ? WHERE id = ?
                """,
                (clean_source, final_text, speaker, score, json.dumps(reasons), status, utc_now(), row["id"]),
            )
            after = dict(db.execute("SELECT * FROM cues WHERE id = ?", (row["id"],)).fetchone())
            db.execute("INSERT INTO audit_log (cue_id, action, before_json, after_json, created_at, reviewer) VALUES (?, ?, ?, ?, ?, ?)",
                       (row["id"], "legacy_speaker_migration", json.dumps(dict(row)), json.dumps(after), utc_now(), "System migration — not human verification"))
    print(f"{'Normalized' if args.apply else 'Preview only; would normalize'} speaker prefixes on {changed} untouched machine cue(s).")


if __name__ == "__main__":
    main()
