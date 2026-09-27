from pathlib import Path

from uniscribe.domain.models import Lecture
from uniscribe.domain.usecases import ProcessLecture
from uniscribe.services.transcription import LocalDeterministicTranscriber


def test_process_lecture_keeps_raw_and_filtered_transcript(tmp_path: Path) -> None:
    audio = tmp_path / "lecture.wav"
    audio.write_bytes(b"RIFF0000WAVEfixture")
    lecture = Lecture(
        id="lecture-1",
        course_id="course-1",
        title="Aula",
        audio_path=str(audio),
        recorded_at_millis=1,
    )
    raw = (
        "Então, pessoal,hum,uh, a constante é 3.14. "
        "Uma repetição repetida repetida. "
        "Talvez isso seja uma hipótese. "
        "Exemplo: x elevado ao quadrado é x ao quadrado."
    )
    result = ProcessLecture(LocalDeterministicTranscriber({audio: raw}))(lecture)

    assert result.transcript.text == raw
    assert result.transcript.filtered_text is not None
    assert "3.14" in result.transcript.filtered_text
    assert "Hipótese" in result.transcript.filtered_text or "hipótese" in result.transcript.filtered_text
    assert result.summary.lecture_id == lecture.id
    assert result.summary.source_transcript_id == result.transcript.id
    assert result.summary.bullets


def test_empty_transcription_is_an_explicit_error(tmp_path: Path) -> None:
    audio = tmp_path / "empty.wav"
    audio.write_bytes(b"RIFF0000WAVE")
    lecture = Lecture("l", "c", "t", str(audio), 0)
    pipeline = ProcessLecture(LocalDeterministicTranscriber(default_text=""))
    try:
        pipeline(lecture)
    except Exception as exc:
        assert exc.__class__.__name__ == "EmptyTranscriptError"
    else:
        raise AssertionError("empty transcription should not produce a summary")


def test_structured_remote_summary_is_mapped_without_losing_fields() -> None:
    from uniscribe.domain.models import Transcript
    from uniscribe.domain.usecases import GenerateLectureSummary

    class RemoteSummarizer:
        def summarize(self, _text):
            return {
                "title": "Aula",
                "summary": "Resumo fiel",
                "definitions": ["Definição"],
                "formulas": ["E = mc²"],
                "questions": ["Dúvida?"],
                "uncertainties": ["Talvez"],
            }

    result = GenerateLectureSummary(RemoteSummarizer())(
        Transcript("t", "l", "pt-BR", "texto")
    )
    assert result.title == "Aula"
    assert result.final_summary == "Resumo fiel"
    assert result.definitions == ["Definição"]
    assert result.formulas == ["E = mc²"]
    assert result.detected_questions == ["Dúvida?"]
    assert result.uncertainties == ["Talvez"]
