# Security and Privacy

## Supported version

Security fixes are applied to the latest `1.x` version. This is an early public release, not a security certification or institutional approval to process identifiable research data. The app's source code is MIT-licensed; bundled media retains separate terms.

## Data-handling model

- The interface and API bind to `127.0.0.1`; they are not designed for LAN or internet exposure.
- The application does not send recording or transcript content to a speech API.
- The application scripts disable Next.js telemetry.
- Model weights may be downloaded from Hugging Face on first use. Standard network metadata such as IP address and request headers can therefore reach that provider, but the application does not attach research files to that request.
- On Unix-like systems, application data directories are restricted to the current OS account and files to owner read/write.
- The default export excludes original media. All transcript exports remain research data and may still identify participants.
- The application does not provide encryption at rest, user authentication, role-based access, remote access control, automatic anonymisation, retention enforcement, or secure deletion.

## Defences in this release

- Loopback-only services, strict expected host names, expected browser origins, no credentialed CORS, and `no-store` responses.
- Uploaded names are reduced to safe leaf names; database media paths must resolve inside the application data directory before serving or packaging.
- Media and optional speaker tracks are probed before acceptance; source VTT files are bounded and must contain timed captions.
- Partial or rejected imports are removed.
- Project and cue input lengths and timing boundaries are validated.
- Reprocessing cannot overwrite any manual edit, saved draft, unclear decision, or verified cue. Revision checks reject stale editor writes.
- Downloads use Unicode-safe content-disposition headers; CSV text that begins with spreadsheet formula prefixes is escaped.
- Package manifests include SHA-256 checksums for integrity checking, not authenticity.
- Dependencies are pinned and audited in continuous integration.
- Repository guards inspect staged blob content, working files, symlinks, common secret patterns, and reachable commit history before push. Reviewed-file exceptions never skip content checks. They are conservative guardrails, not a claim to detect all sensitive information.
- Practice mode uses a separate database and port with a public, attributed sample. Its model-generated captions are never presented as a human reference.

## Threat boundaries

The local-only design does not protect against a compromised operating system, malware running as the same OS user, an attacker with access to an unlocked account, malicious browser extensions, untrusted model or package supply chains, or unauthorized copies made outside the application. File permissions are defence in depth, not encryption.

Run the product only on an institutionally approved, patched, encrypted device. Apply the study's consent, data-management, access, retention, and breach-response requirements. Store any participant identity crosswalk separately.

## Reporting a vulnerability

Report security concerns privately to the repository owner, using GitHub's private vulnerability-reporting feature when available. Do not open a public issue containing participant data, local paths that reveal identities, transcripts, recordings, database files, model caches, or unredacted screenshots. Use a synthetic reproduction and state the affected version.
