import argparse
import os
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--practice", action="store_true")
    args = parser.parse_args()
    if args.practice:
        os.environ["TRS_DATA_DIR"] = str(Path.home() / "Library" / "Application Support" / "Transcript Review Studio Practice")
        os.environ["TRS_PRACTICE"] = "1"
    else:
        os.environ.pop("TRS_PRACTICE", None)
    import uvicorn
    from transcript_review.main import app

    if os.name != "nt":
        os.umask(0o077)
    uvicorn.run(app, host="127.0.0.1", port=8766 if args.practice else 8765, log_level="info")
