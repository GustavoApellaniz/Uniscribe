"""Audio lifecycle and chunk primitives for the Python side of UniScribe.

The Android client is responsible for microphone permission and PCM/MediaRecorder
work.  This module manages temporary paths and validates/submit audio files that
arrive at the backend.  It intentionally does not pretend that touching a file
is a recording: ``is_valid_audio_file`` can reject the empty placeholder files
created by older versions of the prototype.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from uuid import uuid4


class AudioRecordingError(RuntimeError):
    """Raised when an audio recording lifecycle operation is invalid."""


@dataclass(frozen=True)
class AudioChunk:
    """An ordered, transport-neutral audio chunk.

    ``sequence`` starts at zero for a lecture and must be unique within one
    upload.  The payload is kept as bytes so a backend can forward it without
    interpreting a provider-specific container format.
    """

    sequence: int
    payload: bytes
    mime_type: str = "audio/wav"
    sample_rate_hz: int = 16_000
    channels: int = 1

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("chunk sequence cannot be negative")
        if not isinstance(self.payload, bytes) or not self.payload:
            raise ValueError("chunk payload must contain bytes")
        if not self.mime_type.startswith("audio/"):
            raise ValueError("chunk mime_type must be an audio media type")
        if self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        if self.channels not in (1, 2):
            raise ValueError("channels must be 1 or 2")


class AudioChunkBuffer:
    """Small in-memory buffer that keeps chunks ordered and detects gaps."""

    def __init__(self, expected_chunks: int | None = None) -> None:
        if expected_chunks is not None and expected_chunks < 0:
            raise ValueError("expected_chunks cannot be negative")
        self.expected_chunks = expected_chunks
        self._chunks: dict[int, AudioChunk] = {}

    def add(self, chunk: AudioChunk) -> None:
        if not isinstance(chunk, AudioChunk):
            raise TypeError("chunk must be an AudioChunk")
        if chunk.sequence in self._chunks:
            raise ValueError(f"duplicate audio chunk sequence: {chunk.sequence}")
        self._chunks[chunk.sequence] = chunk

    def ordered(self) -> tuple[AudioChunk, ...]:
        return tuple(self._chunks[index] for index in sorted(self._chunks))

    def concatenated(self) -> bytes:
        return b"".join(chunk.payload for chunk in self.ordered())

    def is_complete(self) -> bool:
        if self.expected_chunks is None:
            return False
        return set(self._chunks) == set(range(self.expected_chunks))

    def validate_complete(self) -> tuple[AudioChunk, ...]:
        chunks = self.ordered()
        if self.expected_chunks is None:
            raise ValueError("expected_chunks was not configured")
        if not self.is_complete():
            missing = sorted(set(range(self.expected_chunks)) - set(self._chunks))
            raise ValueError(f"missing audio chunks: {missing}")
        return chunks


class AudioRecorder:
    """Manage a temporary recording path without claiming microphone access.

    This class is useful for tests and for a client that receives an already
    captured file from Android.  A native recorder should write the actual
    audio bytes to the returned path.  Calling :meth:`start` twice is rejected
    so a previous recording cannot silently be lost.
    """

    def __init__(
        self,
        output_dir: Path | str,
        *,
        clock: Callable[[], int] | None = None,
    ) -> None:
        self._output_dir = Path(output_dir).expanduser()
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._clock = clock or (lambda: int(time.time() * 1000))
        self._current: Path | None = None
        self._started_at_millis: int | None = None
        self._stopped_at_millis: int | None = None
        self.last_duration_millis = 0

    @property
    def output_dir(self) -> Path:
        return self._output_dir

    @property
    def is_recording(self) -> bool:
        return self._current is not None

    @property
    def current_path(self) -> Path | None:
        return self._current

    def now_millis(self) -> int:
        value = int(self._clock())
        if value < 0:
            raise ValueError("clock must return a non-negative timestamp")
        return value

    def start(self) -> Path:
        if self._current is not None:
            raise AudioRecordingError("a recording is already in progress")
        started_at = self.now_millis()
        path = self._output_dir / f"{started_at}.wav"
        if path.exists():
            path = self._output_dir / f"{started_at}-{uuid4().hex[:8]}.wav"
        path.touch()
        self._current = path
        self._started_at_millis = started_at
        self._stopped_at_millis = None
        self.last_duration_millis = 0
        return path

    def stop(self) -> Path | None:
        recording = self._current
        if recording is None:
            self.last_duration_millis = 0
            return None
        stopped_at = self.now_millis()
        started_at = self._started_at_millis or stopped_at
        self.last_duration_millis = max(0, stopped_at - started_at)
        self._stopped_at_millis = stopped_at
        self._current = None
        self._started_at_millis = None
        return recording

    def discard(self) -> bool:
        """Delete the active placeholder/file, if any; return whether removed."""

        path = self.stop()
        if path is None:
            return False
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        return True

    @staticmethod
    def is_valid_audio_file(path: Path | str) -> bool:
        """Return whether a file has at least a plausible audio payload.

        WAV files must contain the RIFF/WAVE signature.  Other formats are
        accepted when non-empty because container validation belongs to the
        transcription provider.
        """

        candidate = Path(path)
        try:
            if not candidate.is_file() or candidate.stat().st_size == 0:
                return False
            if candidate.suffix.lower() == ".wav":
                with candidate.open("rb") as stream:
                    return stream.read(12) == b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE"
        except OSError:
            return False
        return True

    def elapsed_millis(self) -> int:
        if self._started_at_millis is None:
            return self.last_duration_millis
        return max(0, self.now_millis() - self._started_at_millis)


__all__ = [
    "AudioChunk",
    "AudioChunkBuffer",
    "AudioRecorder",
    "AudioRecordingError",
]
