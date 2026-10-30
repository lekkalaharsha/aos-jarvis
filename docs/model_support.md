# Model Support

The Phase 6 model layer is intentionally narrow.

```text
User request
-> intent/planner
-> model adapter if needed
-> structured output
-> validator
-> tool registry
-> permission/risk gate
-> safe tools
-> audit
-> final answer
```

The forbidden path is direct model execution of files, shell, git, memory, or tools.

## Providers

- Local: OpenAI-compatible or Ollama-style HTTP endpoint. Tests mock transport and do not require Ollama.
- Cloud: OpenAI-compatible HTTP endpoint. Disabled by default and requires `model.allow_cloud=true`, `model.cloud.enabled=true`, request `allow_cloud=true`, and API key from the configured environment variable.

## Config

Cloud API key values are not stored in config. The config stores only the environment variable name, such as `OPENAI_API_KEY`.

## Redaction

Before cloud transport, prompts are redacted for API keys, provider tokens, GitHub tokens, AWS keys, private/SSH keys, JWTs, database URLs with credentials, auth headers, cookies, `.env`-style secrets, passwords, and credential-like key/value pairs.

Audit records only categories and counts, not raw secrets.

## Structured Output Validation

Model tool proposals must name an existing registered tool and match the registry's expected args, risk tier, and approval behavior. Unknown tools, raw shell tools, forbidden git operations, invalid structures, and risk override attempts are blocked and audited.

## Audit Events

Phase 6 adds:

- `model.config_update`
- `model.route`
- `model.request`
- `model.response`
- `model.error`
- `model.redaction`
- `model.validation_blocked`

Audit payloads include provider kind, model name, cloud true/false, redaction summary, prompt/response lengths, success/error state, route decision, and blocked reason. They do not include API keys, raw secrets, full unredacted prompts, private keys, cookies, auth headers, or huge responses.
