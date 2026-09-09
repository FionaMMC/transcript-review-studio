# Architecture and Local Data

## Runtime

The launcher starts two loopback-only processes:

1. A Next.js interface on `127.0.0.1:3000`.
2. A FastAPI service on `127.0.0.1:8765`.

The browser talks to the API over localhost. The API validates media with FFprobe, extracts 16 kHz mono audio with FFmpeg, runs the local recognition engine, aligns versions, stores review state in SQLite, serves media previews with range support, and generates exports on demand.

The API accepts browser origins only from the two expected localhost forms and rejects unexpected host headers. Research responses are marked `no-store`.

## Processing flow

```text
media + optional VTT + optional named tracks
                     |
                     v
              validate and copy
                     |
                     v
          FFmpeg normalized local WAV
                     |
          +----------+-----------+
          |                      |
          v                      v
 local STT pass A        local STT pass B
 contextual decoding     alternate context
          |                      |
          +----------+-----------+
                     |
         align against source VTT
       + surface likely VTT omissions
                     |
      optional named-track activity match
                     |
                     v
          ambiguity queue + SQLite
                     |
              human verification
                     |
                     v
       draft/verified analysis package
```

FFmpeg silence detection records speech-region evidence and supports named-track attribution. Whisper word timestamps and source-caption windows currently define review cues.

## Local data structure

On macOS, runtime data is stored here:

```text
~/Library/Application Support/Transcript Review Studio/
├── studio.sqlite3
├── studio.sqlite3-wal              # present only while SQLite needs it
├── studio.sqlite3-shm              # present only while SQLite needs it
└── projects/
    └── <project-id>/
        └── recordings/
            └── <recording-id>/
                ├── media/
                │   └── <original-media-filename>
                ├── source/
                │   └── <source-caption>.vtt       # optional
                ├── speaker-tracks/
                │   └── 01-<track-filename>        # optional
                └── media/processing/
                    └── audio-16k.wav               # local working audio
```

The database contains project/recording metadata, aligned cue versions, statuses, and edit history. The folders contain the supplied evidence and generated working audio. On Unix-like systems, the application applies owner-only permissions (`0700` directories and `0600` files) as defence in depth; it does not encrypt data at rest.

## Source repository boundary

Runtime data is outside the source tree. Git ignores virtual environments, build products, databases, archives, outputs, and local environment files. Tests create synthetic data only. The repository must not be placed inside the research-data directory and must remain separate from other application repositories. Only exact, checksum-approved public sample and promotional-media assets are exempt from the media/archive ban.

## Export boundary

Individual exports are generated in memory. Full packages use a temporary ZIP that is deleted after the response. The default package contains transcripts and source captions but not original media; it is still sensitive research data. The restricted option adds original audio/video and is higher risk.
