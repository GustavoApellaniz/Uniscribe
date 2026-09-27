"""Application use cases for the lecture processing pipeline."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from uniscribe.data.repositories import MemoryStore
from uniscribe.domain.models import Lecture, Summary, Transcript
from uniscribe.services.audio import AudioRecorder
from uniscribe.services.speech import SpeechToTextEngine


class ProcessingError(RuntimeError):
    """Base error for a failed, explicit lecture processing operation."""


class EmptyTranscriptError(ProcessingError):
    """Raised when a provider returns no usable transcript."""


@dataclass(frozen=True)
class ProcessingResult:
    lecture: Lecture
    transcript: Transcript
    summary: Summary


class StartLectureRecording:
    def __init__(
        self,
        recorder: AudioRecorder,
        store: MemoryStore | None = None,
    ) -> None:
        self._recorder = recorder
        self._store = store

    def __call__(self, course_id: str, title: str) -> Lecture:
        if not isinstance(course_id, str) or not course_id.strip():
            raise ValueError("course_id must be a non-empty string")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title must be a non-empty string")
        audio_path = self._recorder.start()
        lecture = Lecture(
            id=str(uuid4()),
            course_id=course_id,
            title=title.strip(),
            audio_path=str(audio_path),
            recorded_at_millis=self._recorder.now_millis(),
        )
        if self._store is not None:
            self._store.save_lecture(lecture)
        return lecture


class StopLectureRecording:
    """Finalize the active recording and update its duration/status."""

    def __init__(
        self,
        recorder: AudioRecorder,
        store: MemoryStore | None = None,
    ) -> None:
        self._recorder = recorder
        self._store = store

    def __call__(self, lecture: Lecture, *, strict: bool = False) -> Lecture:
        path = self._recorder.stop()
        if path is None and strict:
            raise ProcessingError("there is no active recording to stop")
        duration = int(getattr(self._recorder, "last_duration_millis", 0))
        updated = replace(
            lecture,
            audio_path=str(path) if path is not None else lecture.audio_path,
            duration_millis=duration,
            status="stopped" if path is not None else lecture.status,
        )
        if self._store is not None:
            self._store.save_lecture(updated)
        return updated


class TranscribeLecture:
    def __init__(
        self,
        engine: SpeechToTextEngine | Any,
        store: MemoryStore | None = None,
        *,
        allow_empty: bool = True,
    ) -> None:
        self._engine = engine
        self._store = store
        self.allow_empty = allow_empty

    def __call__(self, lecture: Lecture, language_tag: str = "pt-BR") -> Transcript:
        if not isinstance(language_tag, str) or not language_tag.strip():
            raise ValueError("language_tag must be a non-empty string")
        engine_method = getattr(self._engine, "transcribe", None)
        if callable(engine_method):
            text = engine_method(Path(lecture.audio_path), language_tag)
        elif callable(self._engine):
            try:
                text = self._engine(Path(lecture.audio_path), language_tag)
            except TypeError as error:
                # Do not hide a TypeError raised inside a two-argument backend;
                # only retry the explicit one-argument convenience form when
                # introspection says it is supported.
                import inspect

                try:
                    parameters = inspect.signature(self._engine).parameters
                    accepts_one = len(parameters) == 1 or any(
                        parameter.kind == parameter.VAR_POSITIONAL
                        for parameter in parameters.values()
                    )
                except (TypeError, ValueError):
                    accepts_one = False
                if not accepts_one:
                    raise
                text = self._engine(Path(lecture.audio_path))
        else:
            raise TypeError("speech engine must provide transcribe() or be callable")
        if text is None:
            text = ""
        if not isinstance(text, str):
            raise TypeError("speech engine must return a string or None")
        if not self.allow_empty and not text.strip():
            raise EmptyTranscriptError("transcription provider returned no text")
        transcript = Transcript(
            id=str(uuid4()),
            lecture_id=lecture.id,
            language_tag=language_tag,
            text=text,
        )
        if self._store is not None:
            self._store.save_transcript(transcript)
        return transcript


class FilterTranscript:
    """Apply the conservative transcript filter while retaining raw text."""

    def __init__(self, store: MemoryStore | None = None) -> None:
        self._store = store

    def __call__(self, transcript: Transcript) -> Transcript:
        from uniscribe.services.filtering import filter_transcript

        filtered = filter_transcript(transcript.text)
        if hasattr(filtered, "text"):
            filtered = filtered.text
        if not isinstance(filtered, str):
            raise TypeError("transcript filter must return text")
        result = transcript.with_filtered_text(filtered)
        if self._store is not None:
            self._store.save_transcript(result)
        return result


class GenerateLectureSummary:
    """Create a structured summary from the filtered transcript.

    A provider can be injected through ``summarizer``.  The default is the
    deterministic local summarizer, so the MVP remains usable offline and tests
    never call Gemini implicitly.
    """

    def __init__(
        self,
        summarizer: Any | None = None,
        store: MemoryStore | None = None,
    ) -> None:
        self._summarizer = summarizer
        self._store = store

    def __call__(self, transcript: Transcript) -> Summary:
        source = transcript.relevant_text
        if not source.strip():
            raise EmptyTranscriptError("cannot summarize an empty transcript")

        if self._summarizer is None:
            from uniscribe.services.summarization import DeterministicSummarizer

            value = DeterministicSummarizer().summarize(source)
        else:
            method = getattr(self._summarizer, "summarize", None)
            value = method(source) if callable(method) else self._summarizer(source)

        if isinstance(value, Summary):
            result = value
            # Keep the relationship to the supplied transcript explicit even if
            # a custom provider constructed a partial object.
            result.source_transcript_id = transcript.id
            if not result.id:
                result.id = str(uuid4())
        else:
            def as_strings(raw: Any) -> list[str]:
                if raw is None:
                    return []
                if isinstance(raw, str):
                    raw = [raw]
                if not isinstance(raw, (list, tuple, set)):
                    raw = [raw]
                return [str(item).strip() for item in raw if str(item).strip()]

            structured: dict[str, Any] = {}
            if isinstance(value, dict):
                raw_bullets = (
                    value.get("bullets")
                    or value.get("key_points")
                    or value.get("principais")
                    or value.get("important_points")
                    or []
                )
                bullets = as_strings(raw_bullets)
                uncertainties = as_strings(
                    value.get("uncertainties") or value.get("duvidas")
                )
                structured = {
                    "title": str(value.get("title") or "").strip(),
                    "key_concepts": as_strings(
                        value.get("key_concepts") or value.get("concepts")
                    ),
                    "explanations": as_strings(
                        value.get("explanations") or value.get("explicacoes")
                    ),
                    "definitions": as_strings(
                        value.get("definitions") or value.get("definicoes")
                    ),
                    "examples": as_strings(value.get("examples") or value.get("exemplos")),
                    "formulas": as_strings(value.get("formulas")),
                    "important_points": as_strings(
                        value.get("important_points") or value.get("pontos_importantes")
                    ),
                    "detected_questions": as_strings(
                        value.get("detected_questions")
                        or value.get("questions")
                        or value.get("duvidas")
                    ),
                    "final_summary": str(
                        value.get("final_summary")
                        or value.get("summary")
                        or value.get("resumo")
                        or ""
                    ).strip(),
                }
            elif isinstance(value, str):
                bullets = [value.strip()] if value.strip() else []
                uncertainties = []
            elif hasattr(value, "bullets"):
                bullets = as_strings(getattr(value, "bullets", []))
                uncertainties = as_strings(getattr(value, "uncertainties", []))
                structured["final_summary"] = str(
                    getattr(value, "final_summary", "")
                    or getattr(value, "text", "")
                    or getattr(value, "summary", "")
                ).strip()
            else:
                bullets = as_strings(value)
                uncertainties = []
            result = Summary(
                id=str(uuid4()),
                lecture_id=transcript.lecture_id,
                bullets=bullets,
                title=structured.get("title", ""),
                final_summary=(
                    structured.get("final_summary", "")
                    if isinstance(value, dict)
                    else (
                        structured.get("final_summary", "")
                        or str(getattr(value, "final_summary", "")).strip()
                        or str(getattr(value, "text", "")).strip()
                    )
                ),
                uncertainties=uncertainties,
                source_transcript_id=transcript.id,
                **{
                    key: value_
                    for key, value_ in structured.items()
                    if key not in {"title", "final_summary"}
                },
            )
        if self._store is not None:
            self._store.save_summary(result)
        return result


class ProcessLecture:
    """Execute ``audio -> transcript -> filter -> summary`` as one unit."""

    def __init__(
        self,
        transcriber: Any,
        summarizer: Any | None = None,
        store: MemoryStore | None = None,
    ) -> None:
        self._transcribe = TranscribeLecture(transcriber, store, allow_empty=False)
        self._filter = FilterTranscript(store)
        self._summarize = GenerateLectureSummary(summarizer, store)

    def __call__(self, lecture: Lecture, language_tag: str = "pt-BR") -> ProcessingResult:
        transcript = self._transcribe(lecture, language_tag)
        filtered = self._filter(transcript)
        summary = self._summarize(filtered)
        return ProcessingResult(lecture=lecture, transcript=filtered, summary=summary)


# Naming compatible with the Kotlin use-case terminology used elsewhere.
ProcessLectureUseCase = ProcessLecture

__all__ = [
    "EmptyTranscriptError",
    "FilterTranscript",
    "GenerateLectureSummary",
    "ProcessLecture",
    "ProcessLectureUseCase",
    "ProcessingError",
    "ProcessingResult",
    "StartLectureRecording",
    "StopLectureRecording",
    "TranscribeLecture",
]
