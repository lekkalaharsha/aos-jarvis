# AOS-Jarvis

AOS-Jarvis is a local-first, safety-oriented agent platform for controlled
computer and developer workflows. It is designed to keep the user in control:
capabilities are denied by default, risky actions require approval, and
operations are recorded in a tamper-evident audit log.

The project is intended to become a community-driven open-source system. It is
not presented as an unrestricted autonomous assistant. The current design
prioritizes explicit permissions, reviewable plans, bounded tools, and safe
failure over maximum automation.

## Current status

- Phases 0–9: implemented, reviewed, and hardened.
- Phase 10 browser automation: implementation is frozen while independent
  real-Chromium security verification remains pending. It is not marked
  complete.
- Phase 11 screen understanding: active with a bounded, read-only scope for
  explicit screenshot capture, bounded OCR, terminal-error detection, screen
  summaries, and approval-gated fix proposals.
- Continuous screen capture, desktop control, credential automation,
  unrestricted browser automation, remote workspace control, and autonomous
  background operation are not supported by the current contract.

See [PHASE_CONTRACT.md](PHASE_CONTRACT.md), [PROJECT_STATE.md](PROJECT_STATE.md),
and [ROADMAP.md](ROADMAP.md) for the authoritative project state.

## Capabilities

The repository currently contains these capability areas:

- CLI foundation, configuration, diagnostics, evaluation fixtures, and audit
  verification.
- Permission and risk enforcement with deny-by-default behavior.
- Safe file inspection and bounded file-write workflows with snapshots.
- Policy-controlled shell execution.
- Deterministic agent loop and intent handling.
- Audit-derived memory, timeline, and recall tools.
- Read-only project and Git inspection with draft-commit support.
- Configurable local model support and opt-in cloud-compatible model adapters.
- Local read-only dashboard.
- Push-to-talk voice input/output with safety filtering.
- Workspace inspection and explicitly approved local application operations.
- Controlled browser components under the Phase 10 security contract.

Every capability is subject to the phase contract, permission model, risk
tier, and audit requirements. A capability being present in the source tree
does not mean that it is production-ready or enabled for unrestricted use.

## How it works

At a high level, a request follows this path:

1. The CLI or another local interface accepts a user request.
2. The system normalizes the request and identifies an allowed intent.
3. The selected tool validates its arguments and checks capability permissions.
4. The risk engine determines whether the operation is safe, requires
   confirmation, or must be denied.
5. Approved work runs inside the tool's boundary and produces a structured
   result or a safe failure.
6. The operation and outcome are written to the audit log; eligible facts may
   be added to local memory after redaction.

Model output, browser content, OCR text, voice transcription, and external
files are treated as untrusted data. They cannot change permissions or approve
their own actions.

## Requirements

- Python 3.11 or newer
- A supported operating system for the capability being used
- Optional system dependencies for voice and browser features

The safest starting point is the local-only CLI with no cloud model enabled.

## Installation

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1

python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Optional feature dependencies are available separately:

```bash
pip install -e ".[dashboard]"
pip install -e ".[voice]"
pip install -e ".[browser]"
```

Do not place API keys in the repository. Use environment variables and keep
cloud providers disabled unless you explicitly understand the data-flow and
redaction behavior.

## Quick start

```bash
aos --help
aos version
aos doctor
aos config show
aos audit verify
aos eval run
```

Useful command groups include `aos fs`, `aos snapshot`, `aos run`, `aos ask`,
`aos memory`, `aos git`, `aos model`, `aos dashboard`, `aos voice`,
`aos workspace`, and `aos browser`. Check each command's help before using it;
some features are experimental or require explicit approval.

## Development

Install development dependencies and run the checks relevant to your change:

```bash
pip install -e ".[dev]"
python -m pytest -q
python -m compileall aos
```

Before changing code, read:

- [AGENTS.md](AGENTS.md) for roles and phase discipline.
- [CODING_RULES.md](CODING_RULES.md) for implementation rules.
- [SECURITY.md](SECURITY.md) and [SECURITY_BOUNDARIES.md](SECURITY_BOUNDARIES.md)
  for safety boundaries.
- [TASKS.md](TASKS.md) and [PHASE_CONTRACT.md](PHASE_CONTRACT.md) for active
  scope.

Contributors should keep commits focused, add regression tests for behavior
changes, avoid weakening security checks, and document any environment-specific
limitations. Do not commit credentials, local settings, generated caches,
browser profiles, audio recordings, screenshots, or private user data.

## Open-source project requirements

Before treating the repository as a mature public release, the project needs:

- A clearly selected OSI-approved license and a committed `LICENSE` file.
- A complete contribution guide covering setup, tests, coding style, commit
  expectations, and phase approval.
- A Code of Conduct and a security policy with private vulnerability reporting.
- Continuous integration for supported Python versions and security-sensitive
  test suites.
- Reproducible dependency installation with pinned or bounded dependencies and
  documented optional system dependencies.
- Public documentation for configuration, data handling, threat model,
  permissions, audit retention, and model/provider privacy.
- Issue and pull-request templates that require reproduction steps, tests, and
  security impact where applicable.
- Release notes, versioning rules, and a maintainer/reviewer ownership model.
- Secret scanning, dependency scanning, linting, type checking, and a check
  that generated or private artifacts are not published.
- A clear support policy distinguishing stable, experimental, and blocked
  capabilities.

Until these items are completed, users should treat AOS-Jarvis as an active
development project rather than a security-certified product.

## Security and privacy

Security boundaries are part of the product, not optional integrations. The
system is designed around:

- deny-by-default capabilities;
- explicit approval for elevated actions;
- path, command, domain, and project allowlists;
- redaction of secrets before model, memory, or audit storage;
- local-first operation and opt-in cloud access;
- audit records with integrity verification;
- snapshots and rollback-aware file operations where supported; and
- fail-closed behavior when policy or environment checks are uncertain.

Please do not disclose a vulnerability in a public issue first. The repository
must publish a private security contact before announcing a production release.
For now, review [SECURITY.md](SECURITY.md) and include enough detail for a
maintainer to reproduce the issue without including real secrets.

## Project layout

```text
aos/          Python package and CLI
tests/        Unit, integration, and security regression tests
docs/         Phase, architecture, and implementation records
ops/          Environment and verification helpers
```

The phase documents are historical and operational records. The active phase
contract is the source of truth for what may be implemented next.

## License

The repository does not yet declare a final open-source license. Before public
release, the project owner must choose and add an OSI-approved license, then
update this section and the package metadata. Until then, reuse and
redistribution rights should be treated as unspecified.

## Disclaimer

AOS-Jarvis can interact with sensitive local systems when capabilities are
enabled. Review the policies and code for your environment, use least
privilege, and test in a disposable workspace before enabling experimental
features. The project is provided for development and research use while the
security gates remain in progress.
