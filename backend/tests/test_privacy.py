from __future__ import annotations

import importlib.util
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("privacy_check", Path(__file__).resolve().parents[2] / "scripts" / "privacy_check.py")
privacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(privacy)


class PrivacyTests(unittest.TestCase):
    def test_reopening_practice_does_not_recover_a_running_job(self) -> None:
        practice_spec = importlib.util.spec_from_file_location("practice", Path(__file__).resolve().parents[2] / "scripts" / "practice.py")
        practice = importlib.util.module_from_spec(practice_spec)
        practice_spec.loader.exec_module(practice)
        with tempfile.TemporaryDirectory() as directory, patch.object(practice, "PRACTICE_DIR", Path(directory)):
            self.assertFalse(practice.has_existing_workspace())
            database = Path(directory) / "studio.sqlite3"
            with sqlite3.connect(database) as db:
                db.executescript("CREATE TABLE projects (id TEXT); INSERT INTO projects VALUES ('synthetic'); CREATE TABLE recordings (status TEXT); INSERT INTO recordings VALUES ('processing');")
            self.assertTrue(practice.has_existing_workspace())
            with sqlite3.connect(database) as db:
                self.assertEqual(db.execute("SELECT status FROM recordings").fetchone()[0], "processing")

    def test_public_sample_exception_cannot_accept_another_video(self) -> None:
        self.assertTrue(privacy.inspect_content("samples/lua-workshop/public-discussion.webm", b"substituted video"))
        self.assertTrue(privacy.inspect_content("samples/lua-workshop/private-interview.webm", b"private video"))

    def test_reviewed_docs_still_have_content_checked(self) -> None:
        value = b"/" + b"Users/synthetic-user/private-material/"
        self.assertTrue(privacy.inspect_content("README.md", value))

    def test_service_keys_and_credential_assignments_are_blocked(self) -> None:
        for value in (b"sk_" + b"synthetic" * 6, b"sk-" + b"synthetic" * 6, b'api_key = "' + b"synthetic" * 6 + b'"'):
            with self.subTest(kind=value[:3]):
                self.assertTrue(privacy.inspect_content("README.md", value))

    def test_promotional_text_is_still_scanned(self) -> None:
        self.assertTrue(privacy.inspect_content("docs/media/english-script.txt", b"sk_" + b"synthetic" * 6))

    def test_approved_binary_is_exact_and_cannot_be_a_symlink(self) -> None:
        import hashlib
        path = "docs/media/synthetic-approved.mp4"
        payload = b"public synthetic demo"
        with patch.dict(privacy.PUBLIC_SAMPLES, {path: hashlib.sha256(payload).hexdigest()}):
            self.assertEqual(privacy.inspect_content(path, payload), [])
            self.assertTrue(privacy.inspect_content(path, payload + b"private addition"))
            self.assertTrue(privacy.inspect_content(path, payload, mode="120000"))

    def test_binary_and_media_and_symlinks_are_blocked(self) -> None:
        for path, content, mode in (("interview.vtt", b"WEBVTT", "100644"), ("app/a.ts", b"\0data", "100644"), ("public/logo.svg", b"target", "120000")):
            self.assertTrue(privacy.inspect_content(path, content, mode=mode))

    def test_index_and_deleted_history_are_checked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*args):
                subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)

            git("init")
            git("config", "user.email", "test@example.invalid")
            git("config", "user.name", "Synthetic Test")
            (root / "README.md").write_bytes(b"/" + b"Users/synthetic-user/private/")
            git("add", "README.md")
            (root / "README.md").write_text("Safe working copy", encoding="utf-8")
            self.assertTrue(any(item.startswith("index:") for item in privacy.check(root)))
            git("commit", "-m", "Synthetic history test")
            git("add", "README.md")
            git("commit", "-m", "Remove synthetic private path")
            self.assertEqual(privacy.check(root), [])
            self.assertTrue(any(item.startswith("history:") for item in privacy.check(root, history=True)))
