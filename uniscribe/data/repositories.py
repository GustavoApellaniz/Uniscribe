"""Thread-safe in-memory repositories for the headless MVP."""

from __future__ import annotations

from threading import RLock
from typing import TypeVar

from uniscribe.domain.models import Course, Lecture, Note, Summary, Transcript


T = TypeVar("T")


class MemoryStore:
    """A small repository with upsert semantics.

    The store intentionally has no network or filesystem dependency.  It is
    useful as a test double and as a process-local cache; a durable adapter can
    implement the same operations later.  Returned lists are copies so callers
    cannot mutate repository state accidentally.
    """

    def __init__(self) -> None:
        self.courses: list[Course] = []
        self.lectures: list[Lecture] = []
        self.notes: list[Note] = []
        self.transcripts: list[Transcript] = []
        self.summaries: list[Summary] = []
        self._lock = RLock()

    @staticmethod
    def _upsert(items: list[T], item: T, identifier: str) -> None:
        updated = [existing for existing in items if getattr(existing, identifier) != getattr(item, identifier)]
        items[:] = [*updated, item]

    def save_course(self, course: Course) -> None:
        with self._lock:
            self._upsert(self.courses, course, "id")

    def save_lecture(self, lecture: Lecture) -> None:
        with self._lock:
            self._upsert(self.lectures, lecture, "id")

    def save_transcript(self, transcript: Transcript) -> None:
        with self._lock:
            self._upsert(self.transcripts, transcript, "id")

    def save_summary(self, summary: Summary) -> None:
        with self._lock:
            self._upsert(self.summaries, summary, "id")

    def save_note(self, note: Note) -> None:
        with self._lock:
            self._upsert(self.notes, note, "id")

    def lectures_for(self, course_id: str) -> list[Lecture]:
        with self._lock:
            return [item for item in self.lectures if item.course_id == course_id]

    def transcript_for(self, lecture_id: str) -> Transcript | None:
        with self._lock:
            matches = [item for item in self.transcripts if item.lecture_id == lecture_id]
        return matches[-1] if matches else None

    def summaries_for(self, lecture_id: str) -> list[Summary]:
        with self._lock:
            return [item for item in self.summaries if item.lecture_id == lecture_id]

    def notes_for(self, lecture_id: str) -> list[Note]:
        with self._lock:
            return [item for item in self.notes if item.lecture_id == lecture_id]

    def get_lecture(self, lecture_id: str) -> Lecture | None:
        with self._lock:
            return next((item for item in self.lectures if item.id == lecture_id), None)

    def delete_lecture(self, lecture_id: str) -> bool:
        """Delete a lecture and its derived records from this in-memory store."""

        with self._lock:
            before = len(self.lectures)
            self.lectures = [item for item in self.lectures if item.id != lecture_id]
            self.transcripts = [item for item in self.transcripts if item.lecture_id != lecture_id]
            self.summaries = [item for item in self.summaries if item.lecture_id != lecture_id]
            self.notes = [item for item in self.notes if item.lecture_id != lecture_id]
            return len(self.lectures) != before

    def clear(self) -> None:
        with self._lock:
            self.courses.clear()
            self.lectures.clear()
            self.notes.clear()
            self.transcripts.clear()
            self.summaries.clear()


__all__ = ["MemoryStore"]
