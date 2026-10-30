from __future__ import annotations

from dataclasses import replace

import typer
from rich.console import Console
from rich.table import Table

from aos.config.loader import CONFIG_PATH
from aos.model.config import ModelConfig, ProviderSettings, cloud_api_key_present, load_model_config, save_model_config
from aos.model.service import ModelService
from aos.model.types import ModelMessage, ModelProviderKind, ModelRequest

app = typer.Typer(help="Configure and test safe Phase 6 model support.")
console = Console()


def _load() -> ModelConfig:
    return load_model_config(CONFIG_PATH)


@app.command("list")
def list_models() -> None:
    config = _load()
    table = Table(show_header=True, header_style="bold")
    for column in ("kind", "enabled", "provider", "model", "base_url"):
        table.add_column(column)
    table.add_row("local", str(config.local.enabled), config.local.provider, config.local.model, config.local.base_url)
    table.add_row("cloud", str(config.cloud.enabled and config.allow_cloud), config.cloud.provider, config.cloud.model, config.cloud.base_url)
    console.print(table)


@app.command("show")
def show() -> None:
    config = _load()
    console.print(f"default_provider: {config.default_provider.value}")
    console.print(f"allow_cloud: {config.allow_cloud}")
    console.print(f"fallback_provider: {config.fallback_provider.value}")
    console.print(f"max_prompt_chars: {config.max_prompt_chars}")
    console.print(f"max_response_chars: {config.max_response_chars}")
    console.print(f"local: {config.local.provider} {config.local.model} enabled={config.local.enabled}")
    console.print(
        f"cloud: {config.cloud.provider} {config.cloud.model} enabled={config.cloud.enabled and config.allow_cloud} api_key_env={config.cloud.api_key_env}"
    )


@app.command("doctor")
def doctor() -> None:
    config = _load()
    ok = True
    console.print("[green][ok][/green] model config parsed")
    if config.default_provider == ModelProviderKind.CLOUD and not config.allow_cloud:
        ok = False
        console.print("[red][fail][/red] cloud is default but disabled")
    if config.allow_cloud and config.cloud.enabled:
        if cloud_api_key_present(config):
            console.print(f"[green][ok][/green] cloud API key env var is set: {config.cloud.api_key_env}")
        else:
            ok = False
            console.print(f"[red][fail][/red] cloud API key env var is not set: {config.cloud.api_key_env}")
    else:
        console.print("[yellow][warn][/yellow] cloud disabled by default")
    if not ok:
        raise typer.Exit(code=1)


@app.command("test")
def test(
    provider: str = typer.Option("local", "--model", help="local or cloud"),
    dry_run: bool = typer.Option(True, "--dry-run/--real", help="Dry-run avoids network calls."),
) -> None:
    config = _load()
    kind = ModelProviderKind(provider)
    if dry_run:
        console.print(f"dry-run ok: {kind.value} model route can be evaluated without network")
        return
    request = ModelRequest([ModelMessage("user", "Say hello safely.")], "model_test", preferred_provider=kind, allow_cloud=kind == ModelProviderKind.CLOUD)
    response = ModelService(config).generate(request)
    console.print(response.text if response.success else f"failed: {response.error}")
    if not response.success:
        raise typer.Exit(code=1)


@app.command("set-default")
def set_default(provider: str) -> None:
    config = _load()
    kind = ModelProviderKind(provider)
    if kind == ModelProviderKind.CLOUD and not (config.allow_cloud and config.cloud.enabled):
        console.print("blocked: cloud must be explicitly enabled before it can be the default")
        raise typer.Exit(code=1)
    save_model_config(replace(config, default_provider=kind), CONFIG_PATH)
    console.print(f"default provider set to {kind.value}")


@app.command("enable-cloud")
def enable_cloud() -> None:
    config = _load()
    save_model_config(replace(config, allow_cloud=True, cloud=replace(config.cloud, enabled=True)), CONFIG_PATH)
    console.print("cloud model support enabled; API key must come from the configured environment variable")


@app.command("disable-cloud")
def disable_cloud() -> None:
    config = _load()
    replacement = replace(config, allow_cloud=False, cloud=replace(config.cloud, enabled=False))
    if replacement.default_provider == ModelProviderKind.CLOUD:
        replacement = replace(replacement, default_provider=ModelProviderKind.LOCAL)
    if replacement.fallback_provider == ModelProviderKind.CLOUD:
        replacement = replace(replacement, fallback_provider=ModelProviderKind.LOCAL)
    save_model_config(replacement, CONFIG_PATH)
    console.print("cloud model support disabled")


@app.command("set-local")
def set_local(provider: str, model: str, base_url: str = typer.Option(None, "--base-url")) -> None:
    config = _load()
    local = ProviderSettings(True, provider, model, base_url or config.local.base_url)
    save_model_config(replace(config, local=local), CONFIG_PATH)
    console.print(f"local model set to {provider} {model}")


@app.command("set-cloud")
def set_cloud(provider: str, model: str, base_url: str = typer.Option(None, "--base-url")) -> None:
    config = _load()
    cloud = ProviderSettings(config.cloud.enabled, provider, model, base_url or config.cloud.base_url, config.cloud.api_key_env)
    save_model_config(replace(config, cloud=cloud), CONFIG_PATH)
    console.print(f"cloud model set to {provider} {model}; API key value was not stored")
