"""Backward-compatible speech service facade.

The configurable implementation lives in :mod:`uniscribe.services.transcription`.
Keeping this small facade lets existing screens and callers use
``SpeechToTextEngine`` while the backend can inject a real Whisper-compatible
adapter in a test or deployment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from uniscribe.services.transcription import (
    LocalDeterministicTranscriber,
    TranscriptionAdapter,
    TranscriptionBackend,
    TranscriptionError,
)


class SpeechToTextEngine:
    """Compatibility wrapper around :class:`TranscriptionAdapter`.

    With the default local stub, missing files retain the original prototype's
    empty-string behaviour.  Set ``require_existing_file=True`` for a strict
    pipeline that must not turn a missing recording into a successful result.
    """

    def __init__(
        self,
        backend: Optional[TranscriptionBackend] = None,
        *,
        require_existing_file: bool = False,
    ) -> None:
        self._adapter = TranscriptionAdapter(
            backend=backend or LocalDeterministicTranscriber(),
            require_existing_file=require_existing_file,
        )

    @property
    def adapter(self) -> TranscriptionAdapter:
        return self._adapter

    def transcribe(self, audio_file: Path | str, language_tag: str = "pt-BR") -> str:
        path = Path(audio_file)
        if not path.is_file() and not self._adapter.require_existing_file:
            return ""
        return self._adapter.transcribe(path, language_tag=language_tag)


__all__ = ["SpeechToTextEngine", "TranscriptionError"]
