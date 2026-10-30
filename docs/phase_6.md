# Phase 6: Model Support

Phase 6 adds safe configurable model support while preserving the existing AOS-Jarvis safety architecture.

## What Phase 6 Does

- Defines `ModelRequest` and `ModelResponse` as the only provider boundary.
- Adds local and cloud provider adapters.
- Keeps cloud disabled by default.
- Adds model config with environment-variable-only cloud API key references.
- Redacts secrets before cloud transport.
- Routes requests deterministically to local, cloud, blocked, or fallback-local decisions.
- Validates structured model tool proposals through the existing tool registry.
- Adds safe model audit events.
- Adds `aos model ...` CLI commands and optional `aos ask --model ...`.

## What Phase 6 Does Not Do

No voice, dashboard, browser automation, screen understanding, multi-agent system, embeddings/vector database, autonomous coding agent, cloud sync, model marketplace, automatic provider discovery, or unrestricted model tool execution.

## Safety Rule

Models are not executors. A model can return text or structured proposals. AOS-Jarvis validates proposals through the registry, permission engine, risk rules, and safe tools before any action.

## CLI Examples

```bash
python -m aos.interfaces.cli.main model list
python -m aos.interfaces.cli.main model show
python -m aos.interfaces.cli.main model doctor
python -m aos.interfaces.cli.main model test --model local
python -m aos.interfaces.cli.main model disable-cloud
python -m aos.interfaces.cli.main ask --model local "summarize this project"
```

Cloud must be explicitly enabled before `--model cloud` can route successfully.

## Known Limitations

- No real model is required for tests.
- Tests use mocks and dry-run behavior.
- Redaction is best-effort and safety-biased.
- Model output remains untrusted.
- Cloud requires explicit enablement and an API key environment variable.
