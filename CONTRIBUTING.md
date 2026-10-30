# Contributing to AOS-Jarvis

Thank you for helping improve AOS-Jarvis. The project is safety-sensitive and
phase-driven, so contributions must preserve explicit user control and the
documented security boundaries.

## Before you start

Read these files before changing code:

- [AGENTS.md](AGENTS.md) for roles and phase discipline.
- [PHASE_CONTRACT.md](PHASE_CONTRACT.md) for the active scope.
- [CODING_RULES.md](CODING_RULES.md) for implementation rules.
- [SECURITY.md](SECURITY.md) and [SECURITY_BOUNDARIES.md](SECURITY_BOUNDARIES.md)
  for security requirements.
- [TASKS.md](TASKS.md) for current work and known blockers.

Do not implement a future-phase feature without an explicit contract update by
the Human Owner. If the requested change is outside the active phase, open an
issue describing the proposed scope instead.

## Development setup

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1

python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Optional capabilities have separate extras:

```bash
pip install -e ".[dashboard]"
pip install -e ".[voice]"
pip install -e ".[browser]"
```

## Making a change

1. Create a focused branch from `master`.
2. Explain the intended behavior and security impact before making a broad
   change.
3. Keep changes small and avoid unrelated formatting or generated files.
4. Add or update regression tests for behavior changes.
5. Keep secrets, credentials, browser profiles, screenshots, recordings,
   caches, and local settings out of commits.
6. Update the relevant coordination record when the change affects phase
   status, known blockers, or security behavior.
7. Use a clear commit subject describing the change.

## Required checks

Run the checks relevant to the changed files before opening a pull request:

```bash
python -m pytest -q
python -m compileall aos
```

Security-sensitive changes should also include focused tests for denial,
approval, redaction, audit integrity, and fail-closed behavior as applicable.
If a required environment is unavailable, report the exact command and
limitation in the pull request instead of weakening or skipping the check.

## Pull requests

A pull request should include:

- a short summary of what changed and why;
- the active phase or contract item it addresses;
- tests and commands run, including failures or unavailable environments;
- security and privacy implications;
- documentation updates, if user-facing behavior changed; and
- any follow-up work or known limitations.

Reviewers may request contract updates, additional tests, or a narrower scope
before approval. Passing tests alone do not authorize a phase change or relax a
security boundary.

## Security reports

Do not publish exploitable vulnerabilities, credentials, or sensitive
reproduction data in a public issue. Follow [SECURITY.md](SECURITY.md) for the
private reporting process. Until a dedicated private security contact is
published, contact the project owner through the repository's private GitHub
security reporting mechanism.

## License

By contributing, you agree that your contribution is provided under the MIT
License included in this repository.
