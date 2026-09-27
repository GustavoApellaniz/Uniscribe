"""Domain objects used by the UniScribe backend.

The objects in this module are deliberately independent from Kivy, Android and
any AI provider.  They are small dataclasses so the application can be tested
with fakes and later persisted by an adapter without changing the core rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass
class Course:
    id: str
    name: str
    code: str
    professor: str


@dataclass
class Lecture:
    id: str
    course_id: str
    title: str
    audio_path: str
    recorded_at_millis: int
    duration_millis: int = 0
    status: str = "recorded"
    mime_type: str = "audio/wav"
    sample_rate_hz: int = 16_000
    channels: int = 1

    def __post_init__(self) -> None:
        if self.duration_millis < 0:
            raise ValueError("duration_millis cannot be negative")
        if self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        if self.channels not in (1, 2):
            raise ValueError("channels must be 1 or 2")


@dataclass(frozen=True)
class TranscriptSegment:
    """A small, provider-neutral segment of a transcript."""

    text: str
    start_millis: int = 0
    end_millis: int | None = None
    confidence: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError("segment text must be a string")
        if self.start_millis < 0:
            raise ValueError("start_millis cannot be negative")
        if self.end_millis is not None and self.end_millis < self.start_millis:
            raise ValueError("end_millis must be greater than or equal to start_millis")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass
class Transcript:
    id: str
    lecture_id: str
    language_tag: str
    text: str
    filtered_text: str | None = None
    segments: tuple[TranscriptSegment, ...] = ()
    confidence: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError("transcript text must be a string")
        if self.filtered_text is not None and not isinstance(self.filtered_text, str):
            raise TypeError("filtered_text must be a string or None")
        if not isinstance(self.language_tag, str) or not self.language_tag.strip():
            raise ValueError("language_tag must be a non-empty string")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if not isinstance(self.segments, tuple):
            self.segments = tuple(self.segments)

    @property
    def raw_text(self) -> str:
        """Alias that makes the provenance of ``text`` explicit."""

        return self.text

    @property
    def raw_transcript(self) -> str:
        return self.text

    @property
    def filtered_transcript(self) -> str | None:
        return self.filtered_text

    @property
    def relevant_text(self) -> str:
        """Return filtered text when available, otherwise the raw transcript."""

        return self.filtered_text if self.filtered_text is not None else self.text

    def with_filtered_text(self, value: str) -> "Transcript":
        """Return a copy carrying a filtered transcript."""

        return Transcript(
            id=self.id,
            lecture_id=self.lecture_id,
            language_tag=self.language_tag,
            text=self.text,
            filtered_text=value,
            segments=self.segments,
            confidence=self.confidence,
        )


@dataclass
class Note:
    id: str
    lecture_id: str
    content: str
    timestamp_millis: int

    def __post_init__(self) -> None:
        if self.timestamp_millis < 0:
            raise ValueError("timestamp_millis cannot be negative")


@dataclass
class Summary:
    """A structured, source-faithful lecture summary.

    ``bullets`` is retained for compatibility with the original prototype.
    New providers should populate the structured lists when available.  An
    empty list means that the source did not contain enough information to make
    that claim; it must not be filled with invented text.
    """

    id: str
    lecture_id: str
    bullets: list[str] = field(default_factory=list)
    title: str = ""
    key_concepts: list[str] = field(default_factory=list)
    explanations: list[str] = field(default_factory=list)
    definitions: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    formulas: list[str] = field(default_factory=list)
    important_points: list[str] = field(default_factory=list)
    detected_questions: list[str] = field(default_factory=list)
    final_summary: str = ""
    uncertainties: list[str] = field(default_factory=list)
    source_transcript_id: str | None = None

    @property
    def concepts(self) -> list[str]:
        """Readable alias used by API/UI layers."""

        return self.key_concepts

    @concepts.setter
    def concepts(self, value: Iterable[str]) -> None:
        self.key_concepts = list(value)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation without secrets or paths."""

        return {
            "id": self.id,
            "lecture_id": self.lecture_id,
            "title": self.title,
            "bullets": list(self.bullets),
            "key_concepts": list(self.key_concepts),
            "explanations": list(self.explanations),
            "definitions": list(self.definitions),
            "examples": list(self.examples),
            "formulas": list(self.formulas),
            "important_points": list(self.important_points),
            "detected_questions": list(self.detected_questions),
            "final_summary": self.final_summary,
            "uncertainties": list(self.uncertainties),
            "source_transcript_id": self.source_transcript_id,
        }


__all__ = [
    "Course",
    "Lecture",
    "Note",
    "Summary",
    "Transcript",
    "TranscriptSegment",
]
