"""Transcription service boundaries.

This module deliberately contains no Whisper HTTP client and no guessed
endpoint.  A transcription implementation (for example, a local Whisper
process or a service-specific adapter) is supplied by the application through
the :class:`TranscriptionBackend` protocol or a callable.

The local implementation is a deterministic *stub*: it returns explicitly
provided fixture text and otherwise returns an empty string.  An empty result
means that the stub did not recognise any speech; it is not a fabricated
transcription.
"""

from __future__ import annotations

import inspect
import os
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Protocol, Union, runtime_checkable


PathLike = Union[str, os.PathLike]
TranscriptionCallable = Callable[[Path, str], str]


class TranscriptionError(RuntimeError):
    """Base class for transcription service errors."""


class TranscriptionConfigurationError(TranscriptionError, ValueError):
    """Raised when a transcription backend cannot be configured."""


class TranscriptionUnavailableError(TranscriptionError):
    """Raised by a backend that is temporarily unable to transcribe audio."""


@runtime_checkable
class TranscriptionBackend(Protocol):
    """The small interface required by :class:`TranscriptionAdapter`.

    ``audio_file`` is a :class:`~pathlib.Path` so implementations do not need
    to know anything about Android or an HTTP framework.  A backend may return
    an empty string when it has no recognised speech.
    """

    def transcribe(
        self, audio_file: Path, language_tag: str = "pt-BR"
    ) -> str:
        """Transcribe ``audio_file`` and return plain text."""


# A couple of descriptive aliases make the boundary easy to discover without
# coupling callers to a particular implementation name.
SpeechToTextBackend = TranscriptionBackend
TranscriberBackend = TranscriptionBackend


class LocalDeterministicTranscriber:
    """A deterministic, local transcription stub for development and tests.

    The stub never decodes an audio file and never pretends that it performed
    speech recognition.  Callers can provide a mapping of fixture paths to
    known transcript text.  This makes tests reproducible while keeping the
    default result honest (an empty string when no fixture was supplied).

    Args:
        transcripts: Optional mapping whose keys are paths (or path strings)
            and whose values are already-known transcript strings.
        default_text: Optional explicit text to return for paths not in the
            mapping.  It is empty by default and should only be non-empty when
            a caller intentionally supplies known text.
    """

    def __init__(
        self,
        transcripts: Optional[Mapping[PathLike, str]] = None,
        *,
        default_text: str = "",
    ) -> None:
        if not isinstance(default_text, str):
            raise TypeError("default_text must be a string")
        self._default_text = default_text
        self._transcripts: dict[str, str] = {}
        for path, text in (transcripts or {}).items():
            if not isinstance(text, str):
                raise TypeError("transcript fixture values must be strings")
            self._transcripts[self._normalise_path(path)] = text

    @staticmethod
    def _normalise_path(path: PathLike) -> str:
        """Return a stable key for a path without requiring it to exist."""

        raw_path = os.fspath(path)
        if isinstance(raw_path, bytes):
            raw_path = os.fsdecode(raw_path)
        return str(Path(raw_path).expanduser().resolve(strict=False))

    def transcript_for(self, audio_file: PathLike) -> Optional[str]:
        """Return the configured fixture for ``audio_file``, if any."""

        key = self._normalise_path(audio_file)
        if key in self._transcripts:
            return self._transcripts[key]
        # A raw spelling is useful for callers constructing a mapping without
        # touching the filesystem, while the resolved key handles normal
        # temporary-file paths.
        raw_path = os.fspath(audio_file)
        if isinstance(raw_path, bytes):
            raw_path = os.fsdecode(raw_path)
        if raw_path in self._transcripts:
            return self._transcripts[raw_path]
        return None

    def transcribe(
        self, audio_file: Path, language_tag: str = "pt-BR"
    ) -> str:
        """Return fixture text, or an empty string when no fixture exists.

        ``language_tag`` is accepted for protocol compatibility.  The stub
        deliberately does not use it to manufacture language-specific output.
        """

        del language_tag
        configured = self.transcript_for(audio_file)
        if configured is not None:
            return configured
        return self._default_text


# Names that accurately describe the same no-network implementation.
LocalTranscriptionStub = LocalDeterministicTranscriber
LocalStubTranscriber = LocalDeterministicTranscriber
LocalTranscriber = LocalDeterministicTranscriber
DeterministicLocalTranscriber = LocalDeterministicTranscriber
DeterministicTranscriber = LocalDeterministicTranscriber
StubTranscriptionBackend = LocalDeterministicTranscriber


class TranscriptionBackendName(str, Enum):
    """Built-in backend names understood by the adapter."""

    LOCAL = "local"
    STUB = "stub"
    DETERMINISTIC = "deterministic"


def _invoke_callable(
    backend: Callable[..., Any], audio_file: Path, language_tag: str
) -> Any:
    """Call a backend with one or two positional arguments as supported."""

    try:
        signature = inspect.signature(backend)
        positional = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.kind
            in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
        ]
        has_varargs = any(
            parameter.kind == parameter.VAR_POSITIONAL
            for parameter in signature.parameters.values()
        )
    except (TypeError, ValueError):
        positional = []
        has_varargs = True
    if has_varargs or len(positional) >= 2:
        return backend(audio_file, language_tag)
    if len(positional) == 1:
        return backend(audio_file)
    raise TranscriptionConfigurationError(
        "A callable transcription backend must accept (audio_file) "
        "or (audio_file, language_tag)"
    )


def _call_backend(
    backend: Union[TranscriptionBackend, TranscriptionCallable],
    audio_file: Path,
    language_tag: str,
) -> str:
    """Call an injected backend while supporting object and function forms."""

    method = getattr(backend, "transcribe", None)
    if callable(method):
        result = _invoke_callable(method, audio_file, language_tag)
    elif callable(backend):
        # Prefer a two-argument callable, but support simple one-argument test
        # doubles without catching and hiding a TypeError from the backend.
        result = _invoke_callable(backend, audio_file, language_tag)
    else:
        raise TranscriptionConfigurationError(
            "backend must implement transcribe(audio_file, language_tag) "
            "or be callable"
        )

    if result is None:
        # No recognised speech is a valid result for a transcription backend.
        return ""
    if not isinstance(result, str):
        raise TranscriptionError(
            "Transcription backend must return a string or None, got "
            f"{type(result).__name__}"
        )
    return result


def resolve_transcription_backend(
    backend: Optional[Union[str, TranscriptionBackend, TranscriptionCallable]] = None,
    *,
    transcripts: Optional[Mapping[PathLike, str]] = None,
    default_text: str = "",
) -> Union[TranscriptionBackend, TranscriptionCallable]:
    """Resolve a built-in name or return an injected backend unchanged.

    Only local deterministic backends are built in.  In particular, this
    function intentionally does not translate a name such as ``"whisper"``
    into an HTTP URL: callers must provide the real backend implementation.
    """

    if backend is None:
        return LocalDeterministicTranscriber(
            transcripts=transcripts, default_text=default_text
        )
    if isinstance(backend, str):
        name = backend.strip().lower().replace("_", "-")
        if name in {"local", "stub", "deterministic", "local-deterministic"}:
            return LocalDeterministicTranscriber(
                transcripts=transcripts, default_text=default_text
            )
        if name == "whisper":
            raise TranscriptionConfigurationError(
                "No Whisper endpoint is built in; inject a configured "
                "TranscriptionBackend or callable instead."
            )
        raise TranscriptionConfigurationError(
            f"Unknown transcription backend {backend!r}. Use 'local' or inject "
            "a backend implementing transcribe()."
        )
    if callable(backend) or callable(getattr(backend, "transcribe", None)):
        return backend
    raise TranscriptionConfigurationError(
        "backend must be a backend name, an object with transcribe(), or a callable"
    )


class TranscriptionAdapter:
    """Application-facing adapter around a configurable transcription backend."""

    def __init__(
        self,
        backend: Optional[Union[str, TranscriptionBackend, TranscriptionCallable]] = None,
        *,
        transcripts: Optional[Mapping[PathLike, str]] = None,
        default_text: str = "",
        fallback: Optional[
            Union[TranscriptionBackend, TranscriptionCallable]
        ] = None,
        require_existing_file: bool = True,
    ) -> None:
        self._backend = resolve_transcription_backend(
            backend, transcripts=transcripts, default_text=default_text
        )
        self._fallback = fallback
        self.require_existing_file = bool(require_existing_file)
        if fallback is not None and not (
            callable(fallback) or callable(getattr(fallback, "transcribe", None))
        ):
            raise TranscriptionConfigurationError(
                "fallback must implement transcribe() or be callable"
            )

    @classmethod
    def from_config(
        cls,
        backend: Optional[Union[str, TranscriptionBackend, TranscriptionCallable]] = None,
        **kwargs: object,
    ) -> "TranscriptionAdapter":
        """Construct an adapter from a backend name or injected object."""

        return cls(backend=backend, **kwargs)  # type: ignore[arg-type]

    @property
    def backend(self) -> Union[TranscriptionBackend, TranscriptionCallable]:
        """The injected/resolved backend, exposed for diagnostics only."""

        return self._backend

    def transcribe(
        self, audio_file: PathLike, language_tag: str = "pt-BR"
    ) -> str:
        """Transcribe an audio path through the configured backend.

        Missing files fail explicitly by default.  Set ``require_existing_file``
        to ``False`` only when a backend intentionally handles absent files.
        """

        path = Path(audio_file)
        if self.require_existing_file and not path.is_file():
            raise FileNotFoundError(f"Audio file does not exist: {path}")
        if not isinstance(language_tag, str) or not language_tag.strip():
            raise ValueError("language_tag must be a non-empty string")

        try:
            return _call_backend(self._backend, path, language_tag)
        except (NotImplementedError, TranscriptionUnavailableError):
            if self._fallback is None:
                raise
            return _call_backend(self._fallback, path, language_tag)


# Short, unsurprising names for callers that do not need the longer adapter
# terminology.  They all refer to the same implementation.
TranscriptionService = TranscriptionAdapter
ConfigurableTranscriber = TranscriptionAdapter
Transcriber = TranscriptionAdapter


def transcribe(
    audio_file: PathLike,
    *,
    backend: Optional[Union[str, TranscriptionBackend, TranscriptionCallable]] = None,
    language_tag: str = "pt-BR",
    require_existing_file: bool = True,
) -> str:
    """Convenience function for one-off transcription."""

    return TranscriptionAdapter(
        backend=backend, require_existing_file=require_existing_file
    ).transcribe(audio_file, language_tag=language_tag)


__all__ = [
    "ConfigurableTranscriber",
    "DeterministicLocalTranscriber",
    "DeterministicTranscriber",
    "LocalDeterministicTranscriber",
    "LocalStubTranscriber",
    "LocalTranscriber",
    "LocalTranscriptionStub",
    "SpeechToTextBackend",
    "StubTranscriptionBackend",
    "Transcriber",
    "TranscriberBackend",
    "TranscriptionAdapter",
    "TranscriptionBackend",
    "TranscriptionBackendName",
    "TranscriptionCallable",
    "TranscriptionConfigurationError",
    "TranscriptionError",
    "TranscriptionService",
    "TranscriptionUnavailableError",
    "resolve_transcription_backend",
    "transcribe",
]
