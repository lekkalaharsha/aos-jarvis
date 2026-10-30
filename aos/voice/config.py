"""Voice configuration: dataclass and TOML loader.

All optional-dependency imports are lazy (inside functions) so this module
can be imported even when [voice] extras are not installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class VoiceConfig:
    """Runtime-configurable voice settings."""

    enabled: bool = True

    # STT / TTS provider identifiers
    stt_provider: str = "faster_whisper"
    tts_provider: str = "piper"

    # Model selection — provider-specific identifiers
    stt_model: str = "tiny.en"
    tts_model: str = ""

    # Recording limits
    max_recording_seconds: int = 30
    sample_rate: int = 16_000
    channels: int = 1

    # Safety limits
    min_confidence_destructive: float = 0.85
    tts_max_chars: int = 500

    # Behaviour
    speak_responses: bool = True
    speak_approval_required_message: bool = True


def load_voice_config(config_path: Path | None = None) -> VoiceConfig:
    """Load voice configuration from a TOML file, falling back to defaults.

    Reads the ``[voice]`` table from *config_path*.  Any unknown keys are
    silently ignored so forward-compatibility is maintained.
    """
    cfg = VoiceConfig()

    if config_path is None or not config_path.is_file():
        return cfg

    try:
        import tomllib
    except ImportError:  # Python < 3.11
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            return cfg

    with config_path.open("rb") as fh:
        data = tomllib.load(fh)

    voice_table = data.get("voice", {})
    for key, value in voice_table.items():
        if hasattr(cfg, key):
            setattr(cfg, key, value)

    return cfg
