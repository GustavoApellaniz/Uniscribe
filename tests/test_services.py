import json
from pathlib import Path

import pytest

from uniscribe.services.gemini import (
    GeminiClient,
    GeminiNotConfiguredError,
    GeminiResponseError,
    TransportResponse,
)
from uniscribe.services.summarization import DeterministicSummarizer
from uniscribe.services.transcription import (
    LocalDeterministicTranscriber,
    TranscriptionAdapter,
    TranscriptionConfigurationError,
)


def test_transcription_adapter_uses_injected_fake(tmp_path: Path) -> None:
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"audio")
    adapter = TranscriptionAdapter(LocalDeterministicTranscriber({audio: "olá"}))
    assert adapter.transcribe(audio, "pt-BR") == "olá"


def test_transcription_adapter_rejects_guessed_whisper_endpoint() -> None:
    with pytest.raises(TranscriptionConfigurationError):
        TranscriptionAdapter("whisper")


def test_summarizer_preserves_uncertainty_and_is_deterministic() -> None:
    text = "A soma é 2. Talvez o professor tenha dito 3. Não tenho certeza."
    result = DeterministicSummarizer().summarize(text)
    assert result.text == DeterministicSummarizer().summarize(text).text
    assert any("Talvez" in item for item in result.uncertainties)


def test_gemini_requires_server_key_and_never_returns_it() -> None:
    client = GeminiClient(env={})
    assert not client.is_configured()
    with pytest.raises(GeminiNotConfiguredError):
        client.summarize("Aula sobre derivadas.")
    assert "GEMINI_API_KEY" not in repr(client)


def test_gemini_parses_structured_response_without_exposing_key() -> None:
    captured = {}

    def transport(request):
        captured["request"] = request
        generated = json.dumps(
            {
                "title": "Derivadas",
                "summary": "A transcrição apresenta uma definição de derivada.",
                "key_points": ["A derivada mede a taxa de variação."],
                "uncertainties": [],
            },
            ensure_ascii=False,
        )
        envelope = {"candidates": [{"content": {"parts": [{"text": generated}]}}]}
        return TransportResponse(json.dumps(envelope), 200)

    client = GeminiClient(api_key="server-secret", transport=transport)
    result = client.summarize("Aula sobre derivadas.")
    assert result["title"] == "Derivadas"
    request = captured["request"]
    assert request.headers["x-goog-api-key"] == "server-secret"
    assert "server-secret" not in request.url
    assert "server-secret" not in repr(client)
    assert "server-secret" not in repr(request)


def test_gemini_rejects_non_json_generated_text() -> None:
    envelope = {"candidates": [{"content": {"parts": [{"text": "resumo em prosa"}]}}]}
    client = GeminiClient(
        api_key="server-secret",
        transport=lambda _request: TransportResponse(json.dumps(envelope), 200),
    )
    with pytest.raises(GeminiResponseError):
        client.summarize("Aula.")


def test_gemini_uses_current_interactions_envelope() -> None:
    seen = {}

    def transport(request):
        seen["url"] = request.url
        seen["payload"] = json.loads(request.body)
        return TransportResponse(
            json.dumps(
                {
                    "steps": [
                        {
                            "type": "model_output",
                            "content": [{"type": "text", "text": '{"title":"Aula"}'}],
                        }
                    ]
                }
            ),
            200,
        )

    result = GeminiClient(api_key="secret", transport=transport).summarize("Aula.")
    assert result == {"title": "Aula"}
    assert seen["url"].endswith("/v1beta/interactions")
    assert seen["payload"]["model"] == "gemini-3.8-flash"
    assert seen["payload"]["input"].startswith("Resuma")
    assert seen["payload"]["store"] is False
    assert seen["payload"]["response_format"]["mime_type"] == "application/json"
