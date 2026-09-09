# Contributing

## Privacy first

Never commit recordings, transcripts, participant names, real project databases, model caches, exports, or screenshots containing research data. Tests and issue reports must use synthetic content. Do not weaken the local-only boundary without an explicit product and ethics review.

## Development setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
npm ci
```

Run the backend and interface in separate terminals:

```bash
.venv/bin/python backend/run.py
npm run dev -- --hostname 127.0.0.1
```

Runtime data defaults outside this repository. For development and tests, use a temporary isolated folder:

```bash
TRS_DATA_DIR=/tmp/transcript-review-studio-dev .venv/bin/python backend/run.py
```

## Required checks

```bash
npm run lint
npm run build
npm audit --audit-level=moderate
python3 scripts/privacy_check.py
ruff check backend scripts
PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v
.venv/bin/pip-audit -r backend/requirements.txt --progress-spinner off
```

For changes to import, review, media, navigation, or export, also run the critical workflow in a browser using synthetic media. Check a wide desktop and a narrow layout, keyboard navigation, unsaved-edit protection, draft/verified wording, and the restricted-media confirmation.

## Change rules

- Preserve source, STT A, STT B, and current text as distinct evidence.
- Never infer `verified` from model agreement.
- Never call heuristic recognition scores probabilities or accuracy.
- Keep pending, flagged, and unclear cues visible in all outputs.
- Keep stable segment IDs and document export-schema changes.
- Add regression coverage for every fixed correctness or security defect.
- Do not add cloud telemetry, analytics, uploads, or external APIs by default.

## Pull requests

Explain the user problem, workflow impact, privacy impact, migration impact, verification evidence, and any limitation that remains. A release must update `CHANGELOG.md`, product version, and documentation when behavior or the export contract changes.

## Licence

The application source code and original documentation use the [MIT License](LICENSE). Contributions to those files are submitted under the same licence. The public sample, promotional narration, dependencies and model weights retain their separate licences and notices; do not relicense them as MIT.
