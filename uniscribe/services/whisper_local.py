"""Optional local Whisper adapter.

The dependency is intentionally not added to the MVP requirements: model
files are large and platform-specific.  Deployments that choose local ASR can
install a supported Whisper implementation separately and inject this adapter.
No model download or network call happens at import time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class LocalWhisperError(RuntimeError):
    """Raised when the optional local Whisper runtime is unavailable."""


class LocalWhisperTranscriber:
    """Adapter for the official ``whisper`` Python package when installed."""

    def __init__(
        self,
        *,
        model_name: str = "base",
        model: Any | None = None,
        device: str | None = None,
    ) -> None:
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("model_name must be a non-empty string")
        self.model_name = model_name.strip()
        self._model = model
        self.device = device

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            import whisper  # type: ignore[import-not-found]
        except ImportError as exc:
            raise LocalWhisperError(
                "Local Whisper is not installed; inject another TranscriptionBackend "
                "or install a supported Whisper runtime"
            ) from exc
        options: dict[str, Any] = {"name": self.model_name}
        if self.device:
            options["device"] = self.device
        try:
            self._model = whisper.load_model(**options)
        except Exception as exc:  # provider-specific load errors are opaque
            raise LocalWhisperError("local Whisper model could not be loaded") from exc
        return self._model

    def transcribe(self, audio_file: Path, language_tag: str = "pt-BR") -> str:
        path = Path(audio_file)
        if not path.is_file():
            raise FileNotFoundError(f"audio file does not exist: {path}")
        language = language_tag.split("-", 1)[0] if language_tag else None
        model = self._load_model()
        try:
            result = model.transcribe(str(path), language=language)
        except Exception as exc:
            raise LocalWhisperError("local Whisper transcription failed") from exc
        if isinstance(result, dict):
            text = result.get("text", "")
        else:
            text = getattr(result, "text", "")
        if text is None:
            return ""
        if not isinstance(text, str):
            raise LocalWhisperError("Whisper returned a non-text result")
        return text.strip()


__all__ = ["LocalWhisperError", "LocalWhisperTranscriber"]
