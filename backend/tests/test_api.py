from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from transcript_review import database, main


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temporary.name) / "private-data"
        self.projects_dir = self.data_dir / "projects"
        self.database_path = self.data_dir / "studio.sqlite3"
        self.patchers = [
            patch.object(database, "DATA_DIR", self.data_dir),
            patch.object(database, "PROJECTS_DIR", self.projects_dir),
            patch.object(database, "DATABASE_PATH", self.database_path),
            patch.object(main, "DATA_DIR", self.data_dir),
            patch.object(main, "PROJECTS_DIR", self.projects_dir),
        ]
        for patcher in self.patchers:
            patcher.start()
        database.initialize()
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        self.client.close()
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.temporary.cleanup()

    def create_project(self, name: str = "Research Interviews") -> dict:
        response = self.client.post("/api/projects", json={"name": name})
        self.assertEqual(response.status_code, 201)
        return response.json()

    def seed_recording(self, project_id: str, *, name: str = "访谈一", with_cue: bool = True) -> tuple[str, int | None]:
        recording_id = "recording-1"
        recording_dir = self.projects_dir / project_id / "recordings" / recording_id / "media"
        recording_dir.mkdir(parents=True, exist_ok=True)
        media_path = recording_dir / "访谈.mp4"
        media_path.write_bytes(b"media")
        with database.connection() as db:
            db.execute(
                """
                INSERT INTO recordings (
                    id, project_id, name, media_path, duration_ms, status,
                    processing_stage, processed_percent, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 5000, 'ready', 'Ready for human review', 100, ?, ?, ?)
                """,
                (recording_id, project_id, name, str(media_path), json.dumps({"media_type": "video"}), database.utc_now(), database.utc_now()),
            )
            cue_id = None
            if with_cue:
                cursor = db.execute(
                    """
                    INSERT INTO cues (
                        recording_id, cue_index, start_ms, end_ms, source_text, stt_a_text,
                        stt_b_text, final_text, speaker, confidence_a, confidence_b,
                        ambiguity_score, ambiguity_reasons, status, updated_at
                    ) VALUES (?, 1, 0, 2000, 'Hello', 'Hello', 'Hello', '=2+2',
                              'P01', .9, .9, 0, '[]', 'pending', ?)
                    """,
                    (recording_id, database.utc_now()),
                )
                cue_id = int(cursor.lastrowid)
        return recording_id, cue_id

    def test_health_is_private_and_rejects_cross_site_origin(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["product"], "Transcript Review Studio")
        self.assertEqual(response.headers["cache-control"], "no-store")
        blocked = self.client.get("/api/projects", headers={"Origin": "https://example.org"})
        self.assertEqual(blocked.status_code, 403)

    def test_reviewer_is_trimmed_and_recorded_in_audit_history(self) -> None:
        project = self.create_project()
        updated = self.client.patch(f"/api/projects/{project['id']}", json={"reviewer": "  MM  "})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["reviewer"], "MM")
        _, cue_id = self.seed_recording(project["id"])
        response = self.client.patch(
            f"/api/cues/{cue_id}",
            json={"final_text": "Corrected", "status": "verified", "reviewer": "MM"},
        )
        self.assertEqual(response.status_code, 200)
        history = self.client.get(f"/api/cues/{cue_id}/history")
        self.assertEqual(history.json()[0]["reviewer"], "MM")
        self.assertEqual(history.json()[0]["after"]["final_text"], "Corrected")

    def test_unicode_download_name_and_csv_formula_escape(self) -> None:
        project = self.create_project("中文研究")
        recording_id, _ = self.seed_recording(project["id"])
        response = self.client.get(f"/api/recordings/{recording_id}/export/csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("filename*=UTF-8''", response.headers["content-disposition"])
        self.assertIn("'=2+2", response.content.decode("utf-8-sig"))

    def test_empty_transcript_cannot_be_mislabeled_as_exportable(self) -> None:
        project = self.create_project()
        recording_id, _ = self.seed_recording(project["id"], with_cue=False)
        self.assertEqual(self.client.get(f"/api/recordings/{recording_id}/export/vtt").status_code, 409)
        self.assertEqual(self.client.get(f"/api/projects/{project['id']}/bundle").status_code, 409)

    def test_invalid_source_vtt_is_rejected_without_orphaned_recording(self) -> None:
        project = self.create_project()
        with patch.object(main, "probe_media", return_value={
            "duration_ms": 1000,
            "media_type": "video",
            "video_codec": "h264",
            "audio_codec": "aac",
            "width": 640,
            "height": 360,
        }):
            response = self.client.post(
                f"/api/projects/{project['id']}/recordings",
                files={
                    "media": ("sample.mp4", b"media", "video/mp4"),
                    "source_vtt": ("empty.vtt", b"WEBVTT\n\n", "text/vtt"),
                },
                data={"recording_name": "Test"},
            )
        self.assertEqual(response.status_code, 400)
        recording_root = self.projects_dir / project["id"] / "recordings"
        self.assertFalse(recording_root.exists() and any(recording_root.iterdir()))

    def test_media_path_outside_private_data_directory_is_blocked(self) -> None:
        project = self.create_project()
        recording_id, _ = self.seed_recording(project["id"])
        with database.connection() as db:
            db.execute("UPDATE recordings SET media_path = '/etc/passwd' WHERE id = ?", (recording_id,))
        response = self.client.get(f"/api/recordings/{recording_id}/media")
        self.assertEqual(response.status_code, 400)

    def test_split_preserves_current_editor_values_and_splits_all_evidence(self) -> None:
        project = self.create_project()
        _, cue_id = self.seed_recording(project["id"])
        response = self.client.post(
            f"/api/cues/{cue_id}/split",
            json={
                "split_ms": 1000,
                "start_ms": 0,
                "end_ms": 2000,
                "final_text": "Edited left words edited right words",
                "speaker": "New participant label",
                "reviewer": "QA",
            },
        )
        self.assertEqual(response.status_code, 200)
        cues = response.json()
        self.assertEqual(len(cues), 2)
        self.assertEqual(" ".join(cue["final_text"] for cue in cues), "Edited left words edited right words")
        self.assertEqual(" ".join(cue["source_text"] for cue in cues).strip(), "Hello")
        self.assertTrue(all(cue["speaker"] == "New participant label" for cue in cues))
        self.assertTrue(all(cue["status"] == "pending" for cue in cues))
        history = self.client.get(f"/api/cues/{cue_id}/history").json()
        self.assertEqual(history[0]["action"], "split")
        self.assertEqual(history[0]["reviewer"], "QA")

    def test_whitespace_project_name_is_rejected(self) -> None:
        self.assertEqual(self.client.post("/api/projects", json={"name": "   "}).status_code, 422)

    def test_reprocessing_protects_unclear_and_draft_edits(self) -> None:
        project = self.create_project()
        recording_id, cue_id = self.seed_recording(project["id"])
        for status in ("unclear", "pending"):
            with self.subTest(status=status):
                self.client.patch(f"/api/cues/{cue_id}", json={"final_text": "Human draft", "status": status})
                with patch.object(main, "process_recording") as process:
                    response = self.client.post(f"/api/recordings/{recording_id}/process", json={})
                self.assertEqual(response.status_code, 409)
                process.assert_not_called()

    def test_cues_cannot_be_edited_during_reprocessing(self) -> None:
        project = self.create_project()
        recording_id, cue_id = self.seed_recording(project["id"])
        with database.connection() as db:
            db.execute("UPDATE recordings SET status = 'processing' WHERE id = ?", (recording_id,))
        self.assertEqual(self.client.patch(f"/api/cues/{cue_id}", json={"final_text": "Edit"}).status_code, 409)
        self.assertEqual(self.client.post(f"/api/cues/{cue_id}/split", json={"split_ms": 1000}).status_code, 409)

    def test_stale_editor_cannot_overwrite_newer_review(self) -> None:
        project = self.create_project()
        _, cue_id = self.seed_recording(project["id"])
        first = self.client.patch(f"/api/cues/{cue_id}", json={"final_text": "Newer edit", "expected_revision": 0})
        self.assertEqual(first.status_code, 200)
        stale = self.client.patch(f"/api/cues/{cue_id}", json={"final_text": "Stale edit", "expected_revision": 0})
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.client.get(f"/api/cues/{cue_id}/history").json()[0]["after"]["final_text"], "Newer edit")

    def test_direct_change_export_uses_same_auditable_schema_as_package(self) -> None:
        project = self.create_project()
        recording_id, _ = self.seed_recording(project["id"])
        response = self.client.get(f"/api/recordings/{recording_id}/export/changes")
        self.assertIn("segment_id", response.text.splitlines()[0])
        self.assertIn("reviewer", response.text.splitlines()[0])


if __name__ == "__main__":
    unittest.main()
