# Voice Interface

Phase 8 is local-only push-to-talk. Voice is untrusted and always calls the
agent with `yes=False`; risky actions require visible approval. Raw audio and
transcripts are not audited. TTS redacts secret-shaped text and is bounded.

Lifecycle has one start and one terminal event per started session. Typed
timeouts map to recording, transcription, or synthesis. No overall session
timeout is implemented. Commands: `aos voice doctor`, `devices`, `listen`, and
`speak`. Optional local dependencies: `pip install 'aos-jarvis[voice]'`.
