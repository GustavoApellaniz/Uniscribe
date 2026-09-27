"""Small, dependency-free HTTP boundary for the UniScribe backend.

The mobile clients should call this service rather than Gemini directly.  The
server is intentionally conservative:

* it binds to ``127.0.0.1`` by default;
* it accepts bounded JSON requests and ephemeral audio files;
* it never returns the Gemini credential;
* it can use an injected transcriber and falls back to deterministic local
  summarisation when Gemini is not configured.

Run locally with ``python -m uniscribe.backend``.  The endpoints are UniScribe's
own API, not a claim about a Whisper or Gemini endpoint.
"""

from __future__ import annotations

import base64
import binascii
import hmac
import json
import logging
import os
import socket
import tempfile
from threading import BoundedSemaphore
from email.parser import BytesParser
from email.policy import default as email_policy
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse, urlsplit

from uniscribe.data.repositories import MemoryStore
from uniscribe.domain.models import Lecture, Summary, Transcript
from uniscribe.domain.usecases import (
    EmptyTranscriptError,
    ProcessLecture,
    ProcessingError,
)
from uniscribe.services.audio import AudioChunk, AudioChunkBuffer
from uniscribe.services.gemini import GeminiClient, GeminiError
from uniscribe.services.summarization import SummarizationService

LOGGER = logging.getLogger("uniscribe.backend")
MAX_BODY_BYTES = 25 * 1024 * 1024


class BackendRequestError(ValueError):
    """Invalid client request."""

    def __init__(self, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
        super().__init__(message)
        self.status = int(status)


class ConfiguredSummarizer:
    """Use Gemini when available and retain the deterministic local fallback."""

    def __init__(self, primary: GeminiClient, fallback: Any | None = None) -> None:
        self.primary = primary
        self.fallback = fallback or SummarizationService()

    def summarize(self, transcript: str) -> Any:
        try:
            return self.primary.summarize(transcript)
        except GeminiError:
            return self.fallback.summarize(transcript)


@dataclass(frozen=True)
class BackendConfig:
    host: str = "127.0.0.1"
    port: int = 8080
    max_body_bytes: int = MAX_BODY_BYTES
    auth_token: str | None = None
    keep_audio: bool = False
    request_timeout_seconds: float = 30.0
    max_workers: int = 8
    allowed_origins: tuple[str, ...] = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )

    def __post_init__(self) -> None:
        if not isinstance(self.host, str) or not self.host.strip():
            raise ValueError("host must be a non-empty string")
        if not 0 <= int(self.port) <= 65535:
            raise ValueError("port must be between 0 and 65535")
        if self.max_body_bytes <= 0:
            raise ValueError("max_body_bytes must be positive")
        if self.request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be positive")
        if self.max_workers <= 0:
            raise ValueError("max_workers must be positive")
        if self.auth_token == "":
            raise ValueError("auth_token must be None or a non-empty string")
        if not isinstance(self.allowed_origins, tuple):
            raise ValueError("allowed_origins must be a tuple of origins")
        for origin in self.allowed_origins:
            if not isinstance(origin, str):
                raise ValueError(f"invalid CORS origin: {origin!r}")
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(f"invalid CORS origin: {origin!r}")
        if self.host not in {"127.0.0.1", "localhost", "::1"} and not self.auth_token:
            raise ValueError("a non-loopback backend requires auth_token")


class LectureBackend:
    """Application service used by the HTTP handler and by tests."""

    def __init__(
        self,
        *,
        transcriber: Any | None = None,
        gemini: GeminiClient | None = None,
        store: MemoryStore | None = None,
        summarizer: Any | None = None,
        temp_dir: Path | str | None = None,
        keep_audio: bool = False,
    ) -> None:
        self.store = store or MemoryStore()
        self._temp_dir = Path(temp_dir) if temp_dir is not None else None
        self.keep_audio = keep_audio
        if transcriber is None:
            provider = os.environ.get("UNISCRIBE_TRANSCRIBER", "stub").strip().lower()
            if provider in {"whisper", "whisper-local", "local-whisper"}:
                from uniscribe.services.whisper_local import LocalWhisperTranscriber

                transcriber = LocalWhisperTranscriber()
            elif provider in {"", "stub", "local", "deterministic"}:
                # The default deliberately does not pretend to decode audio.
                from uniscribe.services.transcription import LocalDeterministicTranscriber

                transcriber = LocalDeterministicTranscriber()
            else:
                raise ValueError(
                    "UNISCRIBE_TRANSCRIBER must be stub or whisper-local"
                )
        self._summarizer = summarizer or self._default_summarizer(gemini)
        self._pipeline = ProcessLecture(
            transcriber,
            summarizer=self._summarizer,
            store=self.store,
        )

    @staticmethod
    def _default_summarizer(gemini: GeminiClient | None) -> Any:
        if gemini is not None and gemini.is_configured():
            return ConfiguredSummarizer(gemini)
        return SummarizationService()

    def process_audio(
        self,
        audio: bytes,
        *,
        lecture_id: str,
        course_id: str = "default",
        title: str = "Nova aula",
        language_tag: str = "pt-BR",
    ) -> dict[str, Any]:
        if not isinstance(audio, bytes) or not audio:
            raise BackendRequestError("audio_base64 must decode to a non-empty value")
        if not lecture_id.strip():
            raise BackendRequestError("lecture_id must be non-empty")
        directory = self._temp_dir or Path(tempfile.gettempdir()) / "uniscribe"
        directory.mkdir(parents=True, exist_ok=True)
        safe_prefix = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in lecture_id
        )[:80] or "lecture"
        fd, raw_path = tempfile.mkstemp(
            prefix=f"{safe_prefix}-", suffix=".audio", dir=directory
        )
        os.close(fd)
        path = Path(raw_path)
        try:
            path.write_bytes(audio)
            lecture = Lecture(
                id=lecture_id,
                course_id=course_id,
                title=title,
                audio_path=str(path),
                recorded_at_millis=0,
            )
            self.store.save_lecture(lecture)
            result = self._pipeline(lecture, language_tag)
            return self._result_payload(result)
        finally:
            if not self.keep_audio:
                path.unlink(missing_ok=True)

    def process_chunks(
        self,
        chunks: Sequence[Mapping[str, Any]],
        *,
        lecture_id: str,
        course_id: str = "default",
        title: str = "Nova aula",
        language_tag: str = "pt-BR",
        mime_type: str = "audio/wav",
    ) -> dict[str, Any]:
        """Validate and concatenate ordered chunks before processing them."""

        if not isinstance(chunks, Sequence) or isinstance(chunks, (str, bytes)):
            raise BackendRequestError("chunks must be an array")
        if not chunks:
            raise BackendRequestError("chunks must not be empty")
        buffer = AudioChunkBuffer(expected_chunks=len(chunks))
        for item in chunks:
            if not isinstance(item, Mapping):
                raise BackendRequestError("each chunk must be an object")
            try:
                sequence = int(item["sequence"])
                encoded = item["audio_base64"]
            except (KeyError, TypeError, ValueError) as exc:
                raise BackendRequestError("each chunk needs sequence and audio_base64") from exc
            if not isinstance(encoded, str) or not encoded:
                raise BackendRequestError("chunk audio_base64 is required")
            try:
                payload = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise BackendRequestError(f"chunk {sequence} audio_base64 is invalid") from exc
            try:
                buffer.add(
                    AudioChunk(
                        sequence=sequence,
                        payload=payload,
                        mime_type=str(item.get("mime_type", mime_type)),
                    )
                )
            except (TypeError, ValueError) as exc:
                raise BackendRequestError(str(exc)) from exc
        try:
            ordered = buffer.validate_complete()
        except ValueError as exc:
            raise BackendRequestError(str(exc)) from exc
        return self.process_audio(
            b"".join(chunk.payload for chunk in ordered),
            lecture_id=lecture_id,
            course_id=course_id,
            title=title,
            language_tag=language_tag,
        )

    def process_transcript(
        self,
        transcript: str,
        *,
        lecture_id: str,
        title: str = "Nova aula",
        language_tag: str = "pt-BR",
    ) -> dict[str, Any]:
        """Process an already transcribed lecture (useful for retries/imports)."""

        if not isinstance(transcript, str) or not transcript.strip():
            raise BackendRequestError("transcript must be non-empty")
        if not lecture_id.strip():
            raise BackendRequestError("lecture_id must be non-empty")
        # Keep one path through the same filtering/summarisation code.  The
        # in-process adapter supplies the already-known transcript.
        def existing_transcript(audio_file: Path, _language: str = "pt-BR") -> str:
            return transcript

        lecture = Lecture(
            id=lecture_id,
            course_id="default",
            title=title,
            audio_path="<provided-transcript>",
            recorded_at_millis=0,
        )
        self.store.save_lecture(lecture)
        pipeline = ProcessLecture(
            existing_transcript,
            summarizer=self._summarizer,
            store=self.store,
        )
        result = pipeline(lecture, language_tag)
        return self._result_payload(result)

    @staticmethod
    def _result_payload(result: Any) -> dict[str, Any]:
        summary_text = result.summary.final_summary or "\n".join(
            f"- {item}" for item in result.summary.bullets
        )
        return {
            "lecture": {
                "id": result.lecture.id,
                "title": result.lecture.title,
                "status": result.lecture.status,
            },
            "transcript": {
                "id": result.transcript.id,
                "raw_text": result.transcript.text,
                "filtered_text": result.transcript.filtered_text,
                "language_tag": result.transcript.language_tag,
            },
            "summary": result.summary.to_dict(),
            # Compact aliases keep the Android client independent of the
            # detailed audit fields while the structured objects remain above.
            "data": {
                "transcript": result.transcript.relevant_text,
                "summary": summary_text,
            },
        }


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def make_handler(backend: LectureBackend, config: BackendConfig) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "UniScribeBackend/0.1"

        def setup(self) -> None:
            super().setup()
            self.connection.settimeout(config.request_timeout_seconds)

        def _cors_origin(self) -> str | None:
            origin = self.headers.get("Origin")
            return origin if origin in config.allowed_origins else None

        def _send(self, status: int, payload: Mapping[str, Any]) -> None:
            body = _json_bytes(payload)
            self.send_response(status)
            origin = self._cors_origin()
            if origin:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # noqa: N802
            origin = self._cors_origin()
            if origin is None:
                self.send_response(HTTPStatus.FORBIDDEN)
                self.end_headers()
                return
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Vary", "Origin")
            self.end_headers()

        def _authorised(self) -> bool:
            if config.auth_token is None:
                return True
            supplied = self.headers.get("Authorization", "")
            expected = f"Bearer {config.auth_token}"
            return hmac.compare_digest(supplied, expected)

        def _read_body(self) -> bytes:
            raw_length = self.headers.get("Content-Length")
            try:
                length = int(raw_length or "0")
            except ValueError as exc:
                raise BackendRequestError("invalid Content-Length") from exc
            if length <= 0:
                raise BackendRequestError("request body is required")
            if length > config.max_body_bytes:
                raise BackendRequestError(
                    "request body is too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE
                )
            return self.rfile.read(length)

        def _read_json(self) -> dict[str, Any]:
            body = self._read_body()
            try:
                value = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise BackendRequestError("request body must be valid UTF-8 JSON") from exc
            if not isinstance(value, dict):
                raise BackendRequestError("request JSON must be an object")
            return value

        def _read_multipart(self, content_type: str) -> dict[str, Any]:
            body = self._read_body()
            envelope = (
                f"Content-Type: {content_type}\r\n"
                "MIME-Version: 1.0\r\n\r\n"
            ).encode("ascii", errors="strict") + body
            try:
                message = BytesParser(policy=email_policy).parsebytes(envelope)
            except Exception as exc:
                raise BackendRequestError("multipart body is invalid") from exc
            if not message.is_multipart():
                raise BackendRequestError("multipart body is invalid")
            result: dict[str, Any] = {}
            for part in message.iter_parts():
                name = part.get_param("name", header="content-disposition")
                if not name:
                    continue
                filename = part.get_filename()
                content = part.get_payload(decode=True) or b""
                if filename is not None:
                    result[str(name)] = content
                else:
                    try:
                        result[str(name)] = content.decode("utf-8")
                    except UnicodeDecodeError as exc:
                        raise BackendRequestError(
                            f"multipart field {name!r} is not UTF-8"
                        ) from exc
            return result

        def _read_request(self) -> dict[str, Any]:
            content_type = self.headers.get("Content-Type", "")
            if content_type.lower().startswith("multipart/form-data"):
                return self._read_multipart(content_type)
            return self._read_json()

        def do_GET(self) -> None:  # noqa: N802
            if not self._authorised():
                self._send(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
            if urlparse(self.path).path == "/health":
                self._send(HTTPStatus.OK, {"status": "ok", "service": "uniscribe"})
                return
            self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            if not self._authorised():
                self._send(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
            route = urlparse(self.path).path
            try:
                payload = self._read_request()
                if route == "/v1/process-audio":
                    audio_value = payload.get("audio")
                    if isinstance(audio_value, bytes):
                        audio = audio_value
                    else:
                        encoded = payload.get("audio_base64")
                        if not isinstance(encoded, str) or not encoded:
                            raise BackendRequestError(
                                "audio or audio_base64 is required"
                            )
                        try:
                            audio = base64.b64decode(encoded, validate=True)
                        except (ValueError, binascii.Error) as exc:
                            raise BackendRequestError("audio_base64 is invalid") from exc
                    result = backend.process_audio(
                        audio,
                        lecture_id=str(payload.get("lecture_id", "")),
                        course_id=str(payload.get("course_id", "default")),
                        title=str(payload.get("title", "Nova aula")),
                        language_tag=str(payload.get("language_tag", "pt-BR")),
                    )
                elif route == "/v1/process-transcript":
                    result = backend.process_transcript(
                        str(payload.get("transcript", "")),
                        lecture_id=str(payload.get("lecture_id", "")),
                        title=str(payload.get("title", "Nova aula")),
                        language_tag=str(payload.get("language_tag", "pt-BR")),
                    )
                elif route == "/v1/process-chunks":
                    result = backend.process_chunks(
                        payload.get("chunks", []),
                        lecture_id=str(payload.get("lecture_id", "")),
                        course_id=str(payload.get("course_id", "default")),
                        title=str(payload.get("title", "Nova aula")),
                        language_tag=str(payload.get("language_tag", "pt-BR")),
                        mime_type=str(payload.get("mime_type", "audio/wav")),
                    )
                else:
                    self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                    return
                self._send(HTTPStatus.OK, result)
            except BackendRequestError as exc:
                self._send(exc.status, {"error": str(exc)})
            except (EmptyTranscriptError, ProcessingError, GeminiError) as exc:
                LOGGER.info("processing failed: %s", type(exc).__name__)
                self._send(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(exc)})
            except (TimeoutError, socket.timeout):
                self._send(HTTPStatus.REQUEST_TIMEOUT, {"error": "request timeout"})
            except Exception:
                LOGGER.exception("unexpected backend error")
                self._send(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error"})

        def log_message(self, format: str, *args: Any) -> None:
            LOGGER.info("%s - %s", self.address_string(), format % args)

    return Handler


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    """Threading server with a hard cap on concurrent request handlers."""

    daemon_threads = True

    def __init__(self, server_address, handler_class, *, max_workers: int) -> None:
        self._worker_slots = BoundedSemaphore(max_workers)
        super().__init__(server_address, handler_class)

    def process_request(self, request, client_address) -> None:
        if not self._worker_slots.acquire(blocking=False):
            try:
                request.sendall(
                    b"HTTP/1.1 503 Service Unavailable\r\n"
                    b"Content-Length: 0\r\nConnection: close\r\n\r\n"
                )
            finally:
                request.close()
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._worker_slots.release()
            raise

    def process_request_thread(self, request, client_address) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._worker_slots.release()


def create_server(
    backend: LectureBackend,
    config: BackendConfig | None = None,
) -> BoundedThreadingHTTPServer:
    settings = config or BackendConfig()
    return BoundedThreadingHTTPServer(
        (settings.host, settings.port),
        make_handler(backend, settings),
        max_workers=settings.max_workers,
    )


def main() -> None:
    logging.basicConfig(level=os.environ.get("UNISCRIBE_LOG_LEVEL", "INFO"))
    raw_origins = os.environ.get("UNISCRIBE_ALLOWED_ORIGINS", "")
    allowed_origins = tuple(
        origin.strip()
        for origin in raw_origins.split(",")
        if origin.strip()
    ) or ("http://localhost:3000", "http://127.0.0.1:3000")
    config = BackendConfig(
        host=os.environ.get("UNISCRIBE_HOST", "127.0.0.1"),
        port=int(os.environ.get("UNISCRIBE_PORT", "8080")),
        auth_token=os.environ.get("UNISCRIBE_AUTH_TOKEN") or None,
        request_timeout_seconds=float(os.environ.get("UNISCRIBE_REQUEST_TIMEOUT", "30")),
        max_workers=int(os.environ.get("UNISCRIBE_MAX_WORKERS", "8")),
        allowed_origins=allowed_origins,
    )
    gemini = GeminiClient.from_server_env()
    server = create_server(LectureBackend(gemini=gemini), config)
    LOGGER.info(
        "UniScribe backend listening on %s:%s (Gemini configured: %s)",
        config.host,
        config.port,
        gemini.is_configured(),
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()


__all__ = [
    "BackendConfig",
    "BackendRequestError",
    "BoundedThreadingHTTPServer",
    "ConfiguredSummarizer",
    "LectureBackend",
    "MAX_BODY_BYTES",
    "create_server",
    "make_handler",
]
