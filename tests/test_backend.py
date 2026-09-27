import base64
import json
import threading
import urllib.error
import urllib.request

from uniscribe.backend import (
    BackendConfig,
    BackendRequestError,
    ConfiguredSummarizer,
    LectureBackend,
    create_server,
)
from uniscribe.services.gemini import GeminiError
from uniscribe.services.transcription import LocalDeterministicTranscriber


def test_backend_process_audio_sanitizes_lecture_id_for_temp_file(tmp_path) -> None:
    backend = LectureBackend(
        transcriber=lambda *_args: "texto",
        temp_dir=tmp_path,
    )
    backend.process_audio(b"audio", lecture_id="../../escape")
    assert list(tmp_path.iterdir()) == []


def test_backend_process_audio_uses_same_pipeline_and_removes_temp_file(tmp_path) -> None:
    transcriber = LocalDeterministicTranscriber(
        default_text="A definição importante é 2 + 2 = 4. Talvez seja um exemplo."
    )
    backend = LectureBackend(transcriber=transcriber, temp_dir=tmp_path)
    payload = backend.process_audio(
        b"RIFF0000WAVEfake",
        lecture_id="lecture-http",
        title="Aula",
    )
    assert payload["summary"]["lecture_id"] == "lecture-http"
    assert payload["transcript"]["raw_text"]
    assert list(tmp_path.iterdir()) == []


def test_backend_rejects_empty_base64() -> None:
    backend = LectureBackend(transcriber=lambda *_args: "texto")
    try:
        backend.process_audio(b"", lecture_id="l")
    except BackendRequestError as exc:
        assert "audio" in str(exc)
    else:
        raise AssertionError("empty audio must fail")


def test_configured_summarizer_keeps_local_fallback() -> None:
    class FailingGemini:
        def summarize(self, _text):
            raise GeminiError("offline")

    result = ConfiguredSummarizer(FailingGemini()).summarize("Aula: 2 + 2 = 4.")
    assert "2 + 2 = 4" in result.text


def test_backend_provider_configuration(monkeypatch) -> None:
    monkeypatch.setenv("UNISCRIBE_TRANSCRIBER", "not-a-provider")
    try:
        LectureBackend()
    except ValueError as exc:
        assert "UNISCRIBE_TRANSCRIBER" in str(exc)
    else:
        raise AssertionError("unknown transcriber provider must fail")


def test_backend_can_process_existing_transcript() -> None:
    backend = LectureBackend(transcriber=lambda *_args: "unused")
    result = backend.process_transcript(
        "Professor: uma definição importante. 10/10/2026. Fórmula: E = mc².",
        lecture_id="l2",
    )
    assert result["lecture"]["id"] == "l2"
    assert result["summary"]["source_transcript_id"]


def test_backend_limits_workers_and_request_timeout() -> None:
    config = BackendConfig(request_timeout_seconds=2.5, max_workers=2)
    assert config.request_timeout_seconds == 2.5
    assert config.max_workers == 2
    for kwargs in ({"request_timeout_seconds": 0}, {"max_workers": 0}):
        try:
            BackendConfig(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid resource limits must fail")


def test_non_loopback_backend_requires_auth_token() -> None:
    try:
        BackendConfig(host="0.0.0.0", port=8080)
    except ValueError as exc:
        assert "auth_token" in str(exc)
    else:
        raise AssertionError("public bind must require authentication")
    assert BackendConfig(host="0.0.0.0", port=8080, auth_token="local-test").auth_token


def test_backend_validates_and_concatenates_chunks() -> None:
    backend = LectureBackend(transcriber=lambda *_args: "Aula processada.")
    result = backend.process_chunks(
        [
            {"sequence": 1, "audio_base64": base64.b64encode(b"b").decode()},
            {"sequence": 0, "audio_base64": base64.b64encode(b"a").decode()},
        ],
        lecture_id="chunked",
    )
    assert result["lecture"]["id"] == "chunked"
    try:
        backend.process_chunks(
            [{"sequence": 1, "audio_base64": base64.b64encode(b"b").decode()}],
            lecture_id="gap",
        )
    except BackendRequestError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("a sequence gap must fail")


def test_http_multipart_contract_and_bearer_auth(tmp_path) -> None:
    backend = LectureBackend(
        transcriber=lambda *_args: "Aula: 2 + 2 = 4.",
        temp_dir=tmp_path,
    )
    server = create_server(backend, BackendConfig(port=0, auth_token="test-token"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    boundary = "----UniScribeTest"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="lecture_id"\r\n\r\n'
        "http-lecture\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="audio"; filename="a.m4a"\r\n'
        "Content-Type: audio/mp4\r\n\r\n"
    ).encode() + b"audio" + f"\r\n--{boundary}--\r\n".encode()
    url = f"http://127.0.0.1:{port}/v1/process-audio"
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": "Bearer test-token",
        },
    )
    try:
        request.add_header("Origin", "http://localhost:3000")
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read())
            assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
        assert payload["lecture"]["id"] == "http-lecture"
        assert payload["data"]["summary"]
        preflight = urllib.request.Request(
            url,
            method="OPTIONS",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        with urllib.request.urlopen(preflight) as response:
            assert response.status == 204
        unauthorized = urllib.request.Request(url, data=b"{}", method="POST")
        try:
            urllib.request.urlopen(unauthorized)
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("missing bearer token must be rejected")
    finally:
        server.shutdown()
        server.server_close()
