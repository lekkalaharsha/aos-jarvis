"""CLI commands for the Phase 8 voice interface.

All optional-dependency imports (sounddevice, faster-whisper, piper) are
deferred to the functions that need them.  The module itself — including
the Typer app object — can be imported at any time without activating the
microphone or loading any speech models.
"""

from __future__ import annotations

import sys

import typer
from rich.console import Console

app = typer.Typer(
    name="voice",
    help="Local push-to-talk voice interface (Phase 8). All processing is local-only.",
    no_args_is_help=True,
)

console = Console()


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


@app.command("doctor")
def doctor() -> None:
    """Check voice dependencies, audio devices, and model availability."""
    ok = True

    # sounddevice check
    try:
        import sounddevice as sd  # noqa: F401

        console.print("[green][ok][/green] sounddevice installed")
    except ImportError:
        ok = False
        console.print(
            "[yellow][warn][/yellow] sounddevice not installed — microphone unavailable. "
            "Run: pip install 'aos-jarvis[voice]'"
        )

    # faster-whisper check
    try:
        import faster_whisper  # noqa: F401

        console.print("[green][ok][/green] faster-whisper installed")
    except ImportError:
        ok = False
        console.print(
            "[yellow][warn][/yellow] faster-whisper not installed — STT unavailable. "
            "Run: pip install 'aos-jarvis[voice]'"
        )

    # piper check
    import shutil

    if shutil.which("piper") is not None:
        console.print("[green][ok][/green] piper found on PATH")
    else:
        console.print(
            "[yellow][warn][/yellow] piper not found on PATH — TTS unavailable. "
            "Install piper and ensure it is on PATH."
        )

    if not ok:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# devices
# ---------------------------------------------------------------------------


@app.command("devices")
def devices() -> None:
    """List available audio input and output devices."""
    try:
        import sounddevice as sd
    except ImportError:
        typer.echo(
            "sounddevice is not installed. Run: pip install 'aos-jarvis[voice]'",
            err=True,
        )
        raise typer.Exit(code=1)

    device_list = sd.query_devices()
    if not device_list:
        console.print("No audio devices found.")
        return

    console.print("Audio devices:")
    for i, dev in enumerate(device_list):
        kind = []
        if dev.get("max_input_channels", 0) > 0:
            kind.append("input")
        if dev.get("max_output_channels", 0) > 0:
            kind.append("output")
        kind_str = "/".join(kind) if kind else "unknown"
        console.print(f"  [{i}] {dev['name']} ({kind_str})")


# ---------------------------------------------------------------------------
# listen
# ---------------------------------------------------------------------------


@app.command("listen")
def listen(
    duration: int = typer.Option(30, "--duration", "-d", help="Maximum recording seconds (1-120)."),
    cwd: str = typer.Option(".", "--cwd", help="Working directory for agent routing."),
    model_name: str = typer.Option("tiny.en", "--model", "-m", help="Whisper model name."),
    speak: bool = typer.Option(True, "--speak/--no-speak", help="Speak the response via TTS."),
) -> None:
    """Push-to-talk: press Enter to stop recording, then transcribe and route to agent."""
    if not 1 <= duration <= 120:
        typer.echo("--duration must be between 1 and 120 seconds.", err=True)
        raise typer.Exit(code=2)

    # Lazy import of all optional voice deps.
    try:
        import sounddevice as sd  # noqa: F401
    except ImportError:
        typer.echo(
            "sounddevice is not installed. Run: pip install 'aos-jarvis[voice]'",
            err=True,
        )
        raise typer.Exit(code=1)

    from aos.voice.config import VoiceConfig
    from aos.voice.providers.local_stt import FasterWhisperSTT
    from aos.voice.providers.local_tts import PiperTTS
    from aos.voice.service import VoiceService
    from aos.voice.session import PushToTalkSession, RecordingTimedOutError
    from aos.voice.types import VoiceOutcome

    cfg = VoiceConfig(max_recording_seconds=duration, speak_responses=speak)
    stt = FasterWhisperSTT(model_name=model_name)
    tts = PiperTTS()
    service = VoiceService(stt, tts, cfg)

    console.print(
        f"[bold]Recording[/bold] (up to {duration}s) — press [bold]Enter[/bold] to stop early, "
        "[bold]Ctrl+C[/bold] to cancel."
    )

    with PushToTalkSession(max_duration=duration, sample_rate=cfg.sample_rate) as session:
        try:
            session.start()
        except RuntimeError as exc:
            typer.echo(f"Recording error: {exc}", err=True)
            raise typer.Exit(code=1)

        # Emit started only after preflight passes and session_id exists.
        session_id = session.session_id
        service.record_session_started(session_id, max_duration=duration)

        with service.create_lifecycle(session_id) as lifecycle:
            try:
                input()  # block until user presses Enter
            except KeyboardInterrupt:
                session.cancel()
                lifecycle.cancel(stage="recording")
                console.print("Recording cancelled.")
                raise typer.Exit(code=0)

            try:
                audio = session.stop()
            except RecordingTimedOutError:
                lifecycle.timeout(stage="recording")
                typer.echo("Recording timed out.", err=True)
                raise typer.Exit(code=1)
            except RuntimeError as exc:
                lifecycle.failed(stage="recording")
                typer.echo(f"Recording error: {exc}", err=True)
                raise typer.Exit(code=1)

            console.print("Transcribing...")
            result = service.process_audio(audio, cwd=cwd, session_id=session_id)

            if not result.success:
                if result.outcome == VoiceOutcome.TIMED_OUT:
                    lifecycle.timeout(stage="transcription")
                    typer.echo("Voice recognition timed out.", err=True)
                    raise typer.Exit(code=1)
                lifecycle.failed(stage="processing")
                typer.echo(f"Error: {result.answer}", err=True)
                raise typer.Exit(code=1)

            console.print(f"[dim]Answer:[/dim] {result.answer}")

            if result.blocked:
                console.print(
                    "[yellow][approval required][/yellow] Re-run the command in the terminal "
                    "with explicit approval flags."
                )

            tts_attempted = False
            if speak and cfg.speak_responses and not result.blocked:
                import tempfile

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    out_path = tmp.name

                tts_attempted = True
                try:
                    speech = service.speak(result.answer, out_path, session_id=session_id)
                    if not speech.success:
                        if speech.outcome == VoiceOutcome.TIMED_OUT:
                            lifecycle.timeout(stage="synthesis")
                            console.print("[yellow][warn][/yellow] TTS timed out.")
                            return
                        console.print(f"[yellow][warn][/yellow] TTS failed: {speech.error}")
                    else:
                        _play_audio(out_path)
                finally:
                    import os

                    try:
                        os.unlink(out_path)
                    except OSError:
                        pass

            lifecycle.complete(
                transcript_available=result.transcript_available,
                approval_required=result.blocked,
                tts_attempted=tts_attempted,
            )


# ---------------------------------------------------------------------------
# speak
# ---------------------------------------------------------------------------


@app.command("speak")
def speak_cmd(text: str = typer.Argument(..., help="Text to synthesize and speak.")) -> None:
    """Synthesize and speak arbitrary text via local TTS."""
    import shutil

    if shutil.which("piper") is None:
        typer.echo(
            "piper is not available. Install piper and ensure it is on PATH.",
            err=True,
        )
        raise typer.Exit(code=1)

    import os
    import tempfile

    from aos.voice.providers.local_stt import MockSTT
    from aos.voice.providers.local_tts import PiperTTS
    from aos.voice.service import VoiceService

    stt = MockSTT()  # not used for speak-only path
    tts = PiperTTS()
    service = VoiceService(stt, tts)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        out_path = tmp.name

    try:
        result = service.speak(text, out_path)
        if not result.success:
            typer.echo(f"TTS failed: {result.error}", err=True)
            raise typer.Exit(code=1)
        _play_audio(out_path)
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _play_audio(path: str) -> None:
    """Play a WAV file using the platform's default audio player."""
    import subprocess

    if sys.platform == "darwin":
        subprocess.run(["afplay", path], check=False, timeout=60)  # noqa: S603,S607
    elif sys.platform.startswith("linux"):
        player = None
        import shutil

        for candidate in ("aplay", "paplay", "ffplay"):
            if shutil.which(candidate):
                player = candidate
                break
        if player:
            subprocess.run([player, path], check=False, timeout=60)  # noqa: S603
    elif sys.platform == "win32":
        import winsound

        winsound.PlaySound(path, winsound.SND_FILENAME)
