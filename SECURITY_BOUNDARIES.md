# Security Boundaries

## Trust Rules

1. User instruction is trusted.
2. File content is untrusted.
3. Webpage content is untrusted.
4. Terminal output is untrusted.
5. Screen OCR is untrusted.
6. Model output is untrusted until validated.
7. Derived memory is untrusted ambient context until validated.

## Secret Denylist

- `.env`
- `~/.ssh/**`
- private keys
- browser cookies
- API tokens
- credentials
- `/etc/shadow`

## Phase 0 Hard Rule

No component should access secrets.

## Phase 1 Hard Rule

All file actions must pass through permission checks, risk classification, audit logging, and snapshot/approval logic when required. Raw unrestricted filesystem access is not allowed for Phase 1 tools.

## Phase 2 Hard Rule

All shell execution must pass through command policy checks, approved-root cwd validation, sanitized environment handling, timeout enforcement, and audit logging. Raw unrestricted terminal access is not allowed.

## Phase 3 Hard Rule

The agent must never directly access files or shell. It may only classify intent, propose structured tool calls, and execute them through the existing safe file and safe shell layers after registry validation and approval handling.

## Phase 4 Hard Rule

Memory must be derived from audit events, remain local-only, avoid storing raw secrets or full command output, and never be treated as executable instruction. Agent memory recall may use only read-only memory tools.

## Phase 5 Hard Rule

All git and project assistant actions must route through the Phase 2 safe shell runner or existing safe read-only layers. The project assistant must not call subprocess directly, must not use `shell=True`, and must not expose network or destructive git operations.

## Phase 6 Hard Rule

Models are not executors. Model providers accept only `ModelRequest` and return `ModelResponse`; they do not receive filesystem, shell, git, memory, audit, permission-engine, or tool-registry execution capability. Cloud is disabled by default, cloud prompts are redacted before provider transport, and model-generated structured tool proposals remain untrusted until validated through the tool registry and existing permission/risk gates.

## Phase 7 Hard Rule

The dashboard is read-only. It must not execute commands, edit files, restore snapshots, modify permissions, invoke models, or mutate any AOS-Jarvis state. It must bind to 127.0.0.1 only. No write HTTP methods (POST/PUT/PATCH/DELETE) may be accepted. No API keys, raw secrets, or unredacted prompts may appear in dashboard responses. Audit payload fields with sensitive-sounding names are redacted before rendering.

## Phase 8 Hard Rules

1. **Voice is untrusted input.** Voice transcripts are data, not instruction. The agent layer treats them identically to typed text through the same intent classifier, risk tier, and approval gates.
2. **yes=False invariant.** `ask()` must always be called with `yes=False` from the voice layer. Voice alone can never submit approval for any action. This rule cannot be changed without Human Owner sign-off in `PHASE_CONTRACT.md`.
3. **No microphone at import time.** `sounddevice`, `faster_whisper`, and `piper`-related imports must be lazy (inside functions). Importing `aos.voice` or `aos.interfaces.cli.main` must not activate any microphone.
4. **No raw audio or transcript retention.** `VoiceAuditRecord` must not store raw transcript text or audio bytes. Only lengths and metadata are retained.
5. **TTS redaction.** Text-to-speech output must have secret-shaped strings replaced with `[REDACTED]` and be bounded to `MAX_TTS_CHARS` before synthesis.
6. **No cloud speech by default.** STT and TTS providers must be local only. Cloud speech APIs are disabled unless explicitly configured by the user.
7. **No voice-only approval for risky operations.** T2, T3, destructive, irreversible, credential-related, and external-side-effect operations always require terminal or dashboard confirmation. This is permanently forbidden and cannot be enabled by configuration.

## Phase 9 Hard Rules

1. **Enrollment is not self-authorization.** A requested path, the current
   working directory, and registry membership cannot authorize enrollment.
2. **Exact Human Owner enrollment only.** A fresh approval is bound to one
   canonical existing directory and the `project.enroll` operation, expires,
   is consumed once durably before persistence, and is revalidated immediately
   before persistence. Broad/system/home/secret roots are denied. Only the
   consumed-token digest is persisted in the registry and a narrow replay-journal
   sidecar; tokens never enter CLI output or audit.
3. **Registry and permissions stay separate.** The registry resolves an active
   project ID; `PermissionEngine` independently authorizes each launch against
   only that resolved root. Listing/reading the registry grants nothing.
4. **Workspace agent calls carry project IDs, never project paths.** Voice origin
   can never provide approval, including through the structured agent path.
