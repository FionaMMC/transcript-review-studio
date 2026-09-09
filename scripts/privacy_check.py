"""Fail-closed, local-only release checks. No data is sent to a scanning service."""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEWED_FILES = {
    ".github/pull_request_template.md", "CHANGELOG.md", "CONTRIBUTING.md",
    "README.md", "SECURITY.md", "LICENSE", "backend/requirements-dev.txt",
    "backend/requirements.txt", "backend/tests/fixture.vtt", "docs/ARCHITECTURE.md",
    "docs/PRODUCT.md", "docs/PUBLIC_E2E_TEST.md", "docs/USER_GUIDE.md",
    "docs/MANUAL_TEST.md", "docs/RELEASE_REVIEW.md", "docs/DESIGN.md",
    "docs/GETTING_STARTED.md", "samples/lua-workshop/README.md",
    "docs/media/README.md", "docs/media/english-script.txt", "docs/media/english-captions.srt",
    "package-lock.json", "package.json", "tsconfig.json",
}
SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".css", ".svg", ".yml", ".yaml", ".command"}
SOURCE_NAMES = {".gitignore", "pre-commit", "pre-push"}
BLOCKED_PARTS = {"data", "dist", "node_modules", "outputs", "work", ".next", ".venv", ".wrangler", ".git"}
CONTENT_PATTERNS = (
    ("local user path", re.compile(rb"/" + rb"Users/[^/\s]+/|[A-Za-z]:\\" + rb"Users\\[^\\\s]+\\")),
    ("private key", re.compile(rb"-----BEGIN " + rb"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(rb"(?:gh[pousr]_" + rb"[A-Za-z0-9]{30,}|github_pat_" + rb"[A-Za-z0-9_]{40,})")),
    ("AWS access key", re.compile(rb"(?:AKIA|ASIA)" + rb"[A-Z0-9]{16}")),
    ("service secret key", re.compile(rb"\bsk[_-]" + rb"[A-Za-z0-9_-]{20,}\b")),
    ("credential assignment", re.compile(rb"(?i)(?:api[_-]?key|client[_-]?secret|access[_-]?token|password)\s*[:=]\s*['\"]" + rb"[A-Za-z0-9_+/=-]{16,}['\"]")),
)
MAX_BYTES = 5 * 1024 * 1024
PUBLIC_SAMPLES = {
    # Only this exact, publicly licensed file is approved for the source repository.
    "samples/lua-workshop/public-discussion.webm": "0c40e1a1de259d3b5572b1b69b9708c308f6d4b363cfa3b41517f52e10a4abb0",
    # Public-only promotional assets reviewed separately, never a directory-wide exception.
    "docs/media/product-tour-elevenlabs.mp4": "1c5c5233383e24bc7acabdc8ba3741e42ab505d4118e051994f60f5a791caa30",
    "docs/media/cover.png": "5c6ef1b1e4ebb5a106ffded1dfd4215b1ba800537a02e5b1f1b06b385a088e04",
    "docs/media/editable-video.zip": "3b3f4181f66546343c8429a8c3389f7ed15d5c27072d2d055003b20f15fe45da",
}


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True).stdout


def inspect_content(path: str, content: bytes, *, mode: str = "100644") -> list[str]:
    """An extension exception never bypasses content checks."""
    item = Path(path)
    failures = []
    if mode not in {"100644", "100755"}:
        failures.append(f"symlink, submodule, or unsupported file mode: {path}")
    if any(part in BLOCKED_PARTS or part.startswith((".env", ".venv")) for part in item.parts):
        failures.append(f"private/generated directory or environment file: {path}")
    if path in PUBLIC_SAMPLES:
        if hashlib.sha256(content).hexdigest() != PUBLIC_SAMPLES[path]:
            failures.append(f"public sample does not match its approved checksum: {path}")
        return failures
    if path not in REVIEWED_FILES and item.suffix.lower() not in SOURCE_SUFFIXES and item.name not in SOURCE_NAMES:
        failures.append(f"unreviewed research/export or unsupported file type: {path}")
    if len(content) > MAX_BYTES:
        failures.append(f"unexpected file over 5 MB: {path}")
    if b"\0" in content:
        failures.append(f"unexpected binary content: {path}")
    for label, pattern in CONTENT_PATTERNS:
        if pattern.search(content):
            failures.append(f"{label} found: {path}")
    return failures


def check(root: Path, *, history: bool = False) -> list[str]:
    failures: list[str] = []
    if not (root / ".git").exists():
        return ["No Git index found. Initialise the standalone repository before release checking."]
    for entry in git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, object_id, stage = metadata.decode().split()
        path = raw_path.decode("utf-8")
        if stage != "0":
            failures.append(f"unresolved merge: {path}")
            continue
        failures.extend(f"index: {error}" for error in inspect_content(path, git(root, "cat-file", "blob", object_id), mode=mode))
        working = root / path
        if working.is_symlink():
            failures.append(f"working tree symlink: {path}")
        elif working.is_file():
            failures.extend(f"working tree: {error}" for error in inspect_content(path, working.read_bytes()))
    for raw_path in git(root, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0"):
        if not raw_path:
            continue
        path = raw_path.decode("utf-8")
        working = root / path
        if working.is_symlink():
            failures.append(f"untracked symlink: {path}")
        elif working.is_file():
            failures.extend(f"untracked: {error}" for error in inspect_content(path, working.read_bytes()))
    if history:
        # Deleted files in an earlier commit are still uploaded on a first push.
        for entry in git(root, "rev-list", "--objects", "--all").splitlines():
            object_id, separator, raw_path = entry.partition(b" ")
            if not separator or git(root, "cat-file", "-t", object_id.decode()).strip() != b"blob":
                continue
            path = raw_path.decode("utf-8")
            failures.extend(f"history: {error}" for error in inspect_content(path, git(root, "cat-file", "blob", object_id.decode())))
    return sorted(set(failures))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true", help="Also inspect all reachable committed blobs before publishing")
    args = parser.parse_args()
    try:
        failures = check(ROOT, history=args.history)
    except (OSError, UnicodeError, subprocess.CalledProcessError) as exc:
        print(f"Privacy check could not finish ({type(exc).__name__}). Do not publish.", file=sys.stderr)
        return 1
    if failures:
        print("Privacy check failed. Do not commit or upload:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("Privacy check passed for index, working files" + (", and reachable history." if args.history else "."))
    print("This is a guardrail, not proof of anonymisation. Manually review the staged diff before release.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
