from pathlib import Path

from uniscribe.data.repositories import MemoryStore
from uniscribe.domain.models import Course, Lecture, Note, Summary, Transcript
from uniscribe.services.audio import AudioChunk, AudioChunkBuffer, AudioRecorder
from uniscribe.services.export import export_summary_txt, summary_to_text


def test_memory_store_upserts_and_cascades_delete() -> None:
    store = MemoryStore()
    course = Course("c", "Curso", "C1", "Professor")
    lecture = Lecture("l", "c", "Aula", "/tmp/a.wav", 1)
    transcript = Transcript("t", "l", "pt-BR", "texto")
    note = Note("n", "l", "nota", 1)
    summary = Summary("s", "l", bullets=["ponto"])
    for item, saver in (
        (course, store.save_course),
        (lecture, store.save_lecture),
        (transcript, store.save_transcript),
        (note, store.save_note),
        (summary, store.save_summary),
    ):
        saver(item)  # type: ignore[operator]
    store.save_lecture(Lecture("l", "c", "Aula atualizada", "/tmp/b.wav", 2))
    assert len(store.lectures) == 1
    assert store.get_lecture("l").title == "Aula atualizada"
    assert store.transcript_for("l") is transcript
    assert store.summaries_for("l") == [summary]
    assert store.notes_for("l") == [note]
    assert store.delete_lecture("l")
    assert store.transcript_for("l") is None
    assert store.summaries_for("l") == []


def test_audio_recorder_rejects_double_start_and_stop_is_idempotent(tmp_path: Path) -> None:
    clock_values = iter([100, 250, 300])
    recorder = AudioRecorder(tmp_path, clock=lambda: next(clock_values))
    first = recorder.start()
    assert first.exists()
    try:
        recorder.start()
    except Exception as exc:
        assert exc.__class__.__name__ == "AudioRecordingError"
    else:
        raise AssertionError("double start must fail")
    assert recorder.stop() == first
    assert recorder.last_duration_millis == 150
    assert recorder.stop() is None


def test_audio_chunk_buffer_detects_missing_sequence() -> None:
    buffer = AudioChunkBuffer(expected_chunks=2)
    buffer.add(AudioChunk(0, b"a"))
    try:
        buffer.validate_complete()
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("missing chunk must fail")
    buffer.add(AudioChunk(1, b"b"))
    assert buffer.is_complete()
    assert buffer.concatenated() == b"ab"


def test_export_is_utf8_txt(tmp_path: Path) -> None:
    summary = Summary("s", "l", title="Aula de cálculo", bullets=["A derivada é uma taxa."], uncertainties=["Talvez."])
    text = summary_to_text(summary)
    assert "A derivada" in text
    target = export_summary_txt(summary, tmp_path / "resultado")
    assert target.suffix == ".txt"
    assert target.read_text(encoding="utf-8") == text
