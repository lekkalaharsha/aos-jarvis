# Security Boundaries

## Trust Rules

1. User instruction is trusted.
2. File content is untrusted.
3. Webpage content is untrusted.
4. Terminal output is untrusted.
5. Screen OCR is untrusted.
6. Model output is untrusted until validated.

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

