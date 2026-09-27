"""The small, dependency-injectable Kivy flow used by the MVP.

The home screen deliberately owns the complete, visible MVP flow:

``Start Listening`` -> recording indicator -> ``Stop`` -> ``Processing...`` ->
summary -> ``Copy``/``Export .txt``.

There is no HTTP client or guessed endpoint in this module.  The recorder,
transcriber, summariser, permission checker, connectivity checker, clipboard,
and export directory are all injectable.  The defaults use the local service
boundaries already present in the project (or an honest local fallback), so the
UI can be exercised without a running backend.
"""

from __future__ import annotations

import inspect
import os
import tempfile
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Optional

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView


STATE_IDLE = "idle"
STATE_LISTENING = "listening"
STATE_PROCESSING = "processing"
STATE_READY = "ready"
STATE_ERROR = "error"


class FlowError(RuntimeError):
    """An expected, user-visible MVP flow error."""


class OfflineError(FlowError):
    """Raised when a configured operation explicitly requires connectivity."""


def _safe_error_detail(error: Exception) -> str:
    """Return a short, safe detail suitable for a small status label."""

    detail = str(error).strip()
    if not detail:
        detail = type(error).__name__
    # Avoid allowing a backend exception to make the entire layout unusable.
    return detail[:220]


def _as_path(value: Any) -> Optional[Path]:
    """Best-effort conversion of recorder results to an audio path."""

    if value is None:
        return None
    if isinstance(value, Path):
        return value
    if isinstance(value, bytes):
        try:
            return Path(os.fsdecode(value))
        except (TypeError, ValueError):
            return None
    if isinstance(value, (str, os.PathLike)):
        try:
            return Path(value)
        except (TypeError, ValueError):
            return None
    if isinstance(value, Mapping):
        for key in ("audio_path", "path", "file_path"):
            if key in value:
                return _as_path(value[key])

    # A few injected recorders return a domain Lecture-like object rather than
    # the Path directly.  Supporting these attributes costs no backend coupling.
    for attribute in ("audio_path", "path", "file_path"):
        candidate = getattr(value, attribute, None)
        if candidate is not None:
            return _as_path(candidate)

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            candidate = _as_path(item)
            if candidate is not None:
                return candidate
    return None


def _summary_to_text(value: Any) -> str:
    """Normalise common summary return shapes without inventing content."""

    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    if isinstance(value, str):
        return value.strip()

    for attribute in ("text", "summary", "content", "final_summary"):
        candidate = getattr(value, attribute, None)
        if callable(candidate):
            try:
                candidate = candidate()
            except Exception:
                candidate = None
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    bullets = getattr(value, "bullets", None)
    if callable(bullets):
        try:
            bullets = bullets()
        except Exception:
            bullets = None
    if isinstance(bullets, Sequence) and not isinstance(bullets, (str, bytes, bytearray)):
        cleaned = [str(item).strip() for item in bullets if str(item).strip()]
        if cleaned:
            return "\n".join(f"- {item}" for item in cleaned)

    if isinstance(value, Mapping):
        for key in ("summary", "resumo", "text", "content", "final_summary"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        for key in ("key_points", "principais", "bullets", "points"):
            candidate = value.get(key)
            if isinstance(candidate, Sequence) and not isinstance(
                candidate, (str, bytes, bytearray)
            ):
                cleaned = [str(item).strip() for item in candidate if str(item).strip()]
                if cleaned:
                    return "\n".join(f"- {item}" for item in cleaned)

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if cleaned:
            return "\n".join(cleaned)
    return str(value).strip()


def _transcript_to_text(value: Any) -> str:
    """Extract plain text from a transcriber result."""

    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()

    text = getattr(value, "text", None)
    if callable(text):
        try:
            text = text()
        except Exception:
            text = None
    if isinstance(text, str):
        return text.strip()

    if isinstance(value, Mapping):
        for key in ("text", "transcript", "transcription", "content"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                return candidate.strip()
    raise FlowError("O backend de transcrição devolveu um formato inesperado.")


class _LocalFallbackRecorder:
    """A tiny file-backed fallback used only when the recorder cannot be made."""

    is_fallback = True

    def __init__(self) -> None:
        self._path: Optional[Path] = None

    def start(self) -> Path:
        handle, filename = tempfile.mkstemp(prefix="uniscribe-", suffix=".wav")
        os.close(handle)
        self._path = Path(filename)
        return self._path

    def stop(self) -> Optional[Path]:
        path = self._path
        self._path = None
        return path


class _EmptyTranscriber:
    """An explicit offline fallback that does not pretend to recognise speech."""

    def transcribe(self, audio_file: Path, language_tag: str = "pt-BR") -> str:
        del audio_file, language_tag
        return ""


def _default_recorder() -> Any:
    try:
        from uniscribe.services.audio import AudioRecorder

        recorder = AudioRecorder(Path.home() / ".uniscribe" / "lectures")
        # The Python service owns the path contract; a native recorder must
        # still provide the actual microphone bytes on a device build.
        recorder.is_fallback = True
        return recorder
    except Exception:
        # Desktop/CI environments may not have a writable home directory.  The
        # UI should still be inspectable and the error should remain recoverable.
        return _LocalFallbackRecorder()


def _default_transcriber() -> Any:
    try:
        from uniscribe.services.speech import SpeechToTextEngine

        return SpeechToTextEngine()
    except Exception:
        return _EmptyTranscriber()


def _default_summariser() -> Any:
    try:
        from uniscribe.services.summarization import SummarizationService

        return SummarizationService()
    except Exception:
        return None


class HomeScreen(Screen):
    """Minimal recording and summary screen for the MVP.

    All collaborators are optional keyword dependencies.  They are kept as
    small protocols rather than importing a concrete network service, which
    makes the screen usable with the existing local stubs and with test
    doubles.
    """

    def __init__(
        self,
        recorder: Any = None,
        transcriber: Any = None,
        summariser: Any = None,
        *,
        permission_checker: Any = None,
        network_checker: Any = None,
        require_internet: bool = False,
        export_dir: Any = None,
        clipboard: Any = None,
        language_tag: str = "pt-BR",
        clock: Any = None,
        **kwargs: Any,
    ) -> None:
        # A few callers use the American spelling when injecting a service.
        # Accept it without leaking the alias into Kivy's Widget kwargs.
        if recorder is None:
            recorder = kwargs.pop("audio_recorder", None)
        if recorder is None:
            recorder = kwargs.pop("recording_service", None)
        if summariser is None:
            summariser = kwargs.pop("summarizer", None)
        if summariser is None:
            summariser = kwargs.pop("summary_service", None)
        if summariser is None:
            summariser = kwargs.pop("summary_generator", None)
        if transcriber is None:
            transcriber = kwargs.pop("transcription_backend", None)
        if transcriber is None:
            transcriber = kwargs.pop("transcription_service", None)
        if permission_checker is None:
            permission_checker = kwargs.pop("microphone_permission", None)
        if network_checker is None:
            network_checker = kwargs.pop("connectivity_checker", None)
        if export_dir is None:
            export_dir = kwargs.pop("export_directory", None)

        super().__init__(**kwargs)

        self._recorder = recorder if recorder is not None else _default_recorder()
        self._transcriber = transcriber if transcriber is not None else _default_transcriber()
        self._summariser = (
            summariser if summariser is not None else _default_summariser()
        )
        self._permission_checker = permission_checker
        self._network_checker = network_checker
        self._require_internet = bool(require_internet)
        self._export_dir = export_dir
        self._clipboard = clipboard
        self._language_tag = language_tag or "pt-BR"
        self._clock = clock if clock is not None else Clock

        self.state = STATE_IDLE
        self._processing = False
        self._active_audio_path: Optional[Path] = None
        self._pending_audio_path: Optional[Path] = None
        self._processing_event: Any = None
        self._permission_pending = False
        self._offline_notice = ""
        self._processing_notice = ""
        self._summary_text = ""
        self._transcript_text = ""
        self.last_export_path: Optional[Path] = None
        self.last_result: Optional[dict[str, Any]] = None
        self.last_copied_text: str = ""

        self._build_ui()
        self._apply_state()

    @property
    def recorder(self) -> Any:
        return self._recorder

    @recorder.setter
    def recorder(self, value: Any) -> None:
        self._recorder = value

    @property
    def transcriber(self) -> Any:
        return self._transcriber

    @transcriber.setter
    def transcriber(self, value: Any) -> None:
        self._transcriber = value

    @property
    def summariser(self) -> Any:
        return self._summariser

    @summariser.setter
    def summariser(self, value: Any) -> None:
        self._summariser = value

    @property
    def summary(self) -> str:
        """The currently displayed summary, useful to a host application."""

        return self._summary_text

    @property
    def summary_text(self) -> str:
        """Alias used by export/clipboard integrations."""

        return self._summary_text

    @property
    def is_listening(self) -> bool:
        return self.state == STATE_LISTENING

    @property
    def is_recording(self) -> bool:
        return self.is_listening

    @property
    def is_processing(self) -> bool:
        return self.state == STATE_PROCESSING

    @property
    def is_ready(self) -> bool:
        return self.state == STATE_READY

    def _build_ui(self) -> None:
        root = BoxLayout(
            orientation="vertical",
            padding=[24, 20, 24, 20],
            spacing=10,
        )
        scroll = ScrollView(do_scroll_x=False)
        content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=10,
        )
        content.bind(minimum_height=content.setter("height"))
        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

        content.add_widget(Label(text="UniScribe", font_size="30sp", bold=True))
        content.add_widget(
            Label(
                text="Grave uma aula. O resumo aparece aqui.",
                font_size="15sp",
                size_hint_y=None,
                height=32,
            )
        )

        status_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=42,
            spacing=8,
        )
        self.indicator = Label(
            text="[ Ready ]",
            font_size="17sp",
            size_hint_x=None,
            width=112,
        )
        self.status_label = Label(
            text="Ready to listen",
            font_size="16sp",
            halign="left",
            valign="middle",
        )
        status_row.add_widget(self.indicator)
        status_row.add_widget(self.status_label)
        content.add_widget(status_row)

        self.notice_label = Label(
            text="",
            font_size="13sp",
            color=(0.75, 0.25, 0.18, 1),
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=42,
        )
        content.add_widget(self.notice_label)

        controls = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=54,
            spacing=10,
        )
        self.start_button = Button(text="Start Listening", size_hint_y=None, height=54)
        self.stop_button = Button(text="Stop", size_hint_y=None, height=54)
        self.start_button.bind(on_press=self.start_listening)
        self.stop_button.bind(on_press=self.stop_listening)
        controls.add_widget(self.start_button)
        controls.add_widget(self.stop_button)
        content.add_widget(controls)

        self.processing_label = Label(
            text="Processing...",
            font_size="18sp",
            bold=True,
            size_hint_y=None,
            height=38,
        )
        content.add_widget(self.processing_label)

        content.add_widget(Label(text="Summary", font_size="20sp", bold=True))
        self.summary_label = Label(
            text="Your summary will appear here.",
            font_size="16sp",
            halign="left",
            valign="top",
            size_hint_y=None,
            height=190,
        )
        content.add_widget(self.summary_label)

        actions = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=52,
            spacing=10,
        )
        self.copy_button = Button(text="Copy", size_hint_y=None, height=52)
        self.export_button = Button(text="Export .txt", size_hint_y=None, height=52)
        self.copy_button.bind(on_press=self.copy_summary)
        self.export_button.bind(on_press=self.export_summary)
        actions.add_widget(self.copy_button)
        actions.add_widget(self.export_button)
        content.add_widget(actions)

        # Public aliases make the controls easy to integrate without coupling
        # another screen to Kivy's generated event callbacks.
        self.start_listening_button = self.start_button
        self.stop_listening_button = self.stop_button
        self.copy_button_widget = self.copy_button
        self.export_button_widget = self.export_button
        self.processing_status = self.processing_label
        self.summary_output = self.summary_label
        self.recording_indicator = self.indicator
        self.status = self.status_label
        self.error_label = self.notice_label
        self._indicator = self.indicator
        self._status = self.status_label
        self._start_button = self.start_button
        self._stop_button = self.stop_button
        self._copy_button = self.copy_button
        self._export_button = self.export_button

    def _apply_state(self) -> None:
        """Synchronise all controls after a state transition."""

        if not hasattr(self, "start_button"):
            # Useful for subclasses that call a helper before _build_ui().
            return
        listening = self.state == STATE_LISTENING
        processing = self.state == STATE_PROCESSING
        ready = self.state == STATE_READY

        self.start_button.disabled = listening or processing
        self.stop_button.disabled = not listening
        self.copy_button.disabled = not bool(self._summary_text)
        self.export_button.disabled = not bool(self._summary_text)
        self.processing_label.visible = processing

        if listening:
            self.indicator.text = "[ Listening ]"
            self.indicator.color = (0.1, 0.55, 0.2, 1)
            self.status_label.text = "Listening..."
        elif processing:
            self.indicator.text = "[ Processing ]"
            self.indicator.color = (0.85, 0.45, 0.05, 1)
            self.status_label.text = "Processing..."
            self.processing_label.text = "Processing..."
        elif ready:
            self.indicator.text = "[ Ready ]"
            self.indicator.color = (0.1, 0.35, 0.65, 1)
            self.status_label.text = "Summary ready"
        elif self.state == STATE_ERROR:
            self.indicator.text = "[ Error ]"
            self.indicator.color = (0.75, 0.15, 0.1, 1)
            self.status_label.text = "Something went wrong"
        else:
            self.indicator.text = "[ Ready ]"
            self.indicator.color = (0.35, 0.35, 0.35, 1)
            self.status_label.text = "Ready to listen"

    def _set_state(self, state: str) -> None:
        self.state = state
        self._processing = state == STATE_PROCESSING
        self._apply_state()

    def _set_notice(self, message: str) -> None:
        self.notice_label.text = message or ""
        self.notice_label.visible = bool(message)

    def _clear_summary(self) -> None:
        self._summary_text = ""
        self._transcript_text = ""
        self.last_result = None
        self.last_export_path = None
        self.summary_label.text = "Your summary will appear here."
        self.summary_label.color = (0.35, 0.35, 0.35, 1)
        self._apply_state()

    @staticmethod
    def _permission_result(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        for attribute in ("granted", "allowed", "is_granted", "success"):
            candidate = getattr(value, attribute, None)
            if callable(candidate):
                try:
                    candidate = candidate()
                except Exception:
                    candidate = False
            if candidate is not None:
                return bool(candidate)
        if isinstance(value, str):
            return value.strip().lower() in {
                "granted",
                "allowed",
                "true",
                "yes",
                "ok",
                "permitted",
            }
        return bool(value)

    def _platform_microphone_permission(self) -> tuple[bool, str]:
        """Check Android permission when running under Kivy, otherwise allow it."""

        try:
            from kivy.utils import platform
        except Exception:
            return True, ""

        if platform != "android":
            return True, ""

        try:
            from android.permissions import check_permission, request_permission

            permission = "android.permission.RECORD_AUDIO"
            if bool(check_permission(permission)):
                return True, ""
            try:
                request_permission(permission)
            except TypeError:
                # A few Android/Kivy versions accept a list instead.
                request_permission([permission])
            return False, "Solicitando permissão de microfone. Toque novamente após conceder."
        except Exception as error:
            return False, (
                "Não foi possível verificar a permissão de microfone: "
                f"{_safe_error_detail(error)}"
            )

    def _ensure_microphone_permission(self) -> tuple[bool, str]:
        checker = self._permission_checker
        if checker is None:
            return self._platform_microphone_permission()

        if isinstance(checker, bool):
            if checker:
                return True, ""
            return False, "Permissão de microfone negada. Autorize-a e tente novamente."

        method: Any = None
        result: Any = None
        for name in (
            "ensure_microphone",
            "check_microphone",
            "is_microphone_allowed",
            "is_granted",
            "check",
        ):
            candidate = getattr(checker, name, None)
            if callable(candidate):
                method = candidate
                break
            if candidate is not None:
                result = candidate
                break
        if method is None and callable(checker):
            method = checker
        if method is None and result is None:
            return False, "Não foi possível consultar a permissão de microfone."

        try:
            if method is not None:
                result = method()
        except PermissionError:
            return False, "Permissão de microfone negada. Autorize-a e tente novamente."
        except Exception as error:
            return False, (
                "Não foi possível verificar a permissão de microfone: "
                f"{_safe_error_detail(error)}"
            )

        if self._permission_result(result):
            self._permission_pending = False
            return True, ""
        self._permission_pending = True
        return False, "Permissão de microfone necessária. Autorize-a e toque novamente."

    def on_permission_result(
        self,
        permission: Any = None,
        grant_results: Any = None,
        *args: Any,
    ) -> None:
        """Handle the callback used by Android permission APIs, if available."""

        del permission, args
        if isinstance(grant_results, Sequence) and not isinstance(
            grant_results, (str, bytes, bytearray)
        ):
            granted = bool(grant_results and grant_results[0])
        else:
            granted = bool(grant_results)
        self._permission_pending = False
        if granted:
            self._set_notice("Permissão concedida. Toque em Start Listening.")
        else:
            self._set_state(STATE_IDLE)
            self._set_notice("Permissão de microfone negada. Autorize-a e tente novamente.")

    def _recorder_call(self, action: str) -> Any:
        recorder = self._recorder
        names = ("start", "start_recording") if action == "start" else (
            "stop",
            "stop_recording",
            "finish",
        )
        method: Any = None
        for name in names:
            candidate = getattr(recorder, name, None)
            if callable(candidate):
                method = candidate
                break
        if method is not None:
            return method()
        if action == "start" and callable(recorder):
            return recorder()
        raise FlowError("O gravador injetado não oferece start/stop.")

    def _invoke_transcriber(self, callback: Any, audio_path: Path) -> Any:
        """Call both two-argument and one-argument injected backends."""

        try:
            signature = inspect.signature(callback)
            parameters = list(signature.parameters.values())
        except (TypeError, ValueError):
            return callback(audio_path, self._language_tag)

        positional = [
            parameter
            for parameter in parameters
            if parameter.kind
            in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
        ]
        has_varargs = any(
            parameter.kind == parameter.VAR_POSITIONAL for parameter in parameters
        )
        language_keyword = next(
            (
                parameter
                for parameter in parameters
                if parameter.name == "language_tag"
                and parameter.kind == parameter.KEYWORD_ONLY
            ),
            None,
        )
        if has_varargs or len(positional) >= 2:
            return callback(audio_path, self._language_tag)
        if language_keyword is not None and len(positional) == 1:
            return callback(audio_path, language_tag=self._language_tag)
        if len(positional) == 1:
            return callback(audio_path)
        if language_keyword is not None:
            return callback(language_tag=self._language_tag)
        return callback()

    def _transcribe(self, audio_path: Path) -> str:
        target = self._transcriber
        if target is None:
            target = _default_transcriber()

        if isinstance(target, str):
            try:
                from uniscribe.services.transcription import resolve_transcription_backend

                target = resolve_transcription_backend(target)
            except Exception as error:
                # A named provider is not an excuse to guess an endpoint.  Keep
                # the screen usable with the explicitly empty local fallback.
                target = _EmptyTranscriber()
                self._processing_notice = (
                    "Backend de transcrição não configurado; usando fallback local. "
                    f"{_safe_error_detail(error)}"
                )

        method = getattr(target, "transcribe", None)
        if callable(method):
            result = self._invoke_transcriber(method, audio_path)
        elif callable(target):
            result = self._invoke_transcriber(target, audio_path)
        else:
            raise FlowError("Nenhum backend de transcrição foi injetado.")
        return _transcript_to_text(result)

    def _invoke_summariser(self, callback: Any, transcript: str) -> Any:
        try:
            return callback(transcript)
        except (AttributeError, TypeError) as text_error:
            # The existing domain use case accepts a Transcript object.  Keep
            # that compatibility without requiring it for the MVP contract.
            try:
                from uniscribe.domain.models import Transcript

                domain_transcript = Transcript(
                    id="ui-session",
                    lecture_id="ui-session",
                    language_tag=self._language_tag,
                    text=transcript,
                )
                return callback(domain_transcript)
            except Exception:
                raise text_error

    def _local_summary(self, transcript: str) -> str:
        if not transcript.strip():
            return ""
        try:
            from uniscribe.services.summarization import summarize_text

            return summarize_text(transcript, max_sentences=6).strip()
        except Exception:
            # This fallback is intentionally extractive and does not need any
            # model or network service.
            sentences = [
                part.strip()
                for part in transcript.replace("!", ".").replace("?", ".").split(".")
                if part.strip()
            ]
            return "\n".join(f"- {sentence}" for sentence in sentences[:6])

    def _summarise(self, transcript: str) -> tuple[str, bool]:
        target = self._summariser
        if target is None:
            target = _default_summariser()

        used_fallback = False
        result: Any = None
        if target is not None:
            try:
                method = getattr(target, "summarize", None)
                if callable(method):
                    result = self._invoke_summariser(method, transcript)
                elif callable(target):
                    result = self._invoke_summariser(target, transcript)
                else:
                    raise FlowError("O resumo injetado não oferece summarize().")
            except Exception as error:
                used_fallback = True
                self._processing_notice = (
                    "O resumo principal falhou; foi usado o resumo local. "
                    f"{_safe_error_detail(error)}"
                )

        summary = _summary_to_text(result)
        if not used_fallback and bool(
            getattr(result, "used_fallback", False) or getattr(result, "is_fallback", False)
        ):
            used_fallback = True
        if not summary:
            summary = self._local_summary(transcript)
            used_fallback = used_fallback or bool(summary)
        return summary.strip(), used_fallback

    def _network_available(self) -> Optional[bool]:
        checker = self._network_checker
        if checker is None:
            return None
        if isinstance(checker, bool):
            return checker

        method: Any = None
        result: Any = None
        for name in ("is_available", "available", "is_online", "online", "check"):
            candidate = getattr(checker, name, None)
            if callable(candidate):
                method = candidate
                break
            if candidate is not None:
                result = candidate
                break
        if method is None and callable(checker):
            method = checker
        if method is None and result is None:
            return None
        try:
            if method is not None:
                result = method()
        except Exception:
            # A failed probe is not equivalent to a confirmed offline state;
            # let the injected operation report its own actionable error.
            return None
        if result is None:
            return None
        if isinstance(result, str):
            lowered = result.strip().lower()
            if lowered in {"offline", "false", "no", "unavailable"}:
                return False
            if lowered in {"online", "true", "yes", "available", "ok"}:
                return True
        return bool(result)

    @staticmethod
    def _empty_summary_message() -> str:
        return (
            "Nenhuma fala reconhecida pelo fallback local.\n"
            "O áudio foi encerrado, mas não há texto confiável para resumir."
        )

    @staticmethod
    def _looks_like_network_error(error: Exception) -> bool:
        if isinstance(error, (ConnectionError, TimeoutError)):
            return True
        name = type(error).__name__.lower()
        return any(
            token in name
            for token in ("connection", "timeout", "network", "transport", "unavailable")
        )

    def _friendly_processing_error(self, error: Exception) -> str:
        if isinstance(error, OfflineError):
            return (
                "Sem internet. O processamento foi pausado; tente novamente quando houver conexão."
            )
        if isinstance(error, PermissionError):
            return "Permissão de microfone negada. Autorize-a e grave novamente."
        if isinstance(error, FileNotFoundError):
            return "O áudio não está mais disponível. Inicie uma nova gravação."
        name = type(error).__name__.lower()
        if any(token in name for token in ("connection", "timeout", "unavailable", "network")):
            return "Não foi possível acessar o serviço. Verifique a internet e tente novamente."
        detail = _safe_error_detail(error)
        return f"Não foi possível processar a gravação: {detail}"

    def start_listening(self, *args: Any) -> bool:
        """Start a recording, returning whether the state transition succeeded."""

        del args
        if self.state in {STATE_LISTENING, STATE_PROCESSING}:
            return False

        granted, permission_message = self._ensure_microphone_permission()
        if not granted:
            self._set_state(STATE_IDLE)
            self._set_notice(permission_message)
            self.status_label.text = "Microphone permission required"
            return False

        self._clear_summary()
        self._set_notice("")
        self._active_audio_path = None
        self._pending_audio_path = None
        try:
            started = self._recorder_call("start")
        except PermissionError:
            self._set_state(STATE_IDLE)
            self._set_notice("Permissão de microfone negada. Autorize-a e tente novamente.")
            return False
        except Exception as error:
            self._set_state(STATE_ERROR)
            self._set_notice(f"Não foi possível iniciar a gravação: {_safe_error_detail(error)}")
            return False

        self._active_audio_path = _as_path(started)
        self._set_state(STATE_LISTENING)
        if getattr(self._recorder, "is_fallback", False):
            self._set_notice(
                "Gravação real não está disponível neste ambiente; usando fallback local."
            )
        return True

    def _start(self, *args: Any) -> bool:
        """Backward-compatible callback name for older Kivy integrations."""

        return self.start_listening(*args)

    def _stop(self, *args: Any) -> bool:
        """Backward-compatible callback name for older Kivy integrations."""

        return self.stop_listening(*args)

    def stop_listening(self, *args: Any) -> bool:
        """Stop recording and schedule the visible processing state."""

        del args
        if self.state != STATE_LISTENING:
            self._set_notice("Toque em Start Listening antes de parar.")
            return False

        try:
            stopped = self._recorder_call("stop")
        except Exception as error:
            self._set_state(STATE_ERROR)
            self._set_notice(f"Não foi possível parar a gravação: {_safe_error_detail(error)}")
            return False

        audio_path = _as_path(stopped) or self._active_audio_path
        self._pending_audio_path = audio_path
        self._active_audio_path = None
        self._offline_notice = ""
        self._processing_notice = ""
        self._clear_summary()
        self._set_state(STATE_PROCESSING)
        self.summary_label.text = "Preparing your summary..."
        self.summary_label.color = (0.35, 0.35, 0.35, 1)

        try:
            self._processing_event = self._clock.schedule_once(
                self._process_recording,
                0.05,
            )
        except Exception:
            # A non-Kivy test harness may provide no running Clock.  Keeping the
            # fallback synchronous makes the flow deterministic and still safe.
            self._process_recording()
        return True

    def _process_recording(self, *args: Any) -> None:
        """Transcribe and summarise after the processing label has been shown."""

        del args
        if self.state != STATE_PROCESSING:
            return
        self._processing_event = None

        try:
            connectivity = self._network_available()
            if connectivity is False:
                if self._require_internet:
                    raise OfflineError()
                self._offline_notice = (
                    "Sem internet — usando o fallback local; o resultado pode ser limitado."
                )
            elif connectivity is None and self._require_internet:
                raise OfflineError()

            audio_path = self._pending_audio_path
            if audio_path is None:
                transcript = ""
                self._offline_notice = self._offline_notice or (
                    "O áudio não foi disponibilizado; o resumo usará apenas o fallback local."
                )
            else:
                try:
                    transcript = self._transcribe(audio_path)
                except Exception as error:
                    # A connectivity failure should not take down the screen when
                    # local processing is allowed.  Preserve the explicit
                    # require_internet behaviour for deployments that need it.
                    if not self._require_internet and self._looks_like_network_error(error):
                        transcript = ""
                        self._offline_notice = (
                            "Sem internet — a transcrição remota falhou; usando o fallback local."
                        )
                    else:
                        raise

            # Keep the raw transcript for auditability, but send only the
            # conservatively filtered text to the summariser.
            filtered_transcript = transcript
            try:
                from uniscribe.services.filtering import filter_transcript

                filtered_transcript = filter_transcript(transcript)
            except Exception as error:
                self._processing_notice = (
                    "O filtro local falhou; o resumo usará a transcrição bruta. "
                    f"{_safe_error_detail(error)}"
                )
            summary, used_fallback = self._summarise(filtered_transcript)
            if not summary:
                summary = self._empty_summary_message()
                used_fallback = True
            self._transcript_text = transcript
            self._summary_text = summary
            self.last_result = {
                "audio_path": audio_path,
                "transcript": transcript,
                "filtered_transcript": filtered_transcript,
                "summary": summary,
                "used_fallback": used_fallback,
            }
            self._set_state(STATE_READY)
            self.summary_label.text = summary
            self.summary_label.color = (0.1, 0.1, 0.1, 1)
            notices = [item for item in (self._offline_notice, self._processing_notice) if item]
            self._set_notice(" ".join(notices))
        except Exception as error:
            self._set_state(STATE_ERROR)
            self._summary_text = ""
            self._transcript_text = ""
            self.last_result = None
            self._apply_state()
            self.summary_label.text = "Summary unavailable"
            self.summary_label.color = (0.6, 0.2, 0.15, 1)
            self._set_notice(self._friendly_processing_error(error))

    def process_pending(self) -> None:
        """Process immediately when a host wants to drive the Clock itself."""

        if self.state == STATE_PROCESSING:
            self._process_recording()

    def _copy_text(self, text: str) -> None:
        clipboard = self._clipboard
        if clipboard is None:
            from kivy.core.clipboard import Clipboard

            clipboard = Clipboard
        method = getattr(clipboard, "copy", None)
        if callable(method):
            method(text)
        elif callable(clipboard):
            clipboard(text)
        else:
            raise FlowError("O clipboard não está disponível.")

    def copy_summary(self, *args: Any) -> bool:
        del args
        if not self._summary_text:
            self._set_notice("Não há resumo para copiar ainda.")
            return False
        try:
            self._copy_text(self._summary_text)
        except Exception as error:
            self._set_notice(
                f"Não foi possível copiar: {_safe_error_detail(error)}"
            )
            return False
        self.last_copied_text = self._summary_text
        self._set_notice("Resumo copiado.")
        return True

    def _copy(self, *args: Any) -> bool:
        return self.copy_summary(*args)

    def _export(self, *args: Any) -> Optional[Path]:
        return self.export_summary(*args)

    def _export_directory(self) -> Path:
        directory = self._export_dir
        if callable(directory):
            directory = directory()
        if directory is None:
            try:
                running_app = App.get_running_app()
                user_data_dir = getattr(running_app, "user_data_dir", None)
                if user_data_dir:
                    directory = Path(user_data_dir) / "exports"
            except Exception:
                directory = None
        if directory is None:
            directory = Path.home() / ".uniscribe" / "exports"
        return Path(directory).expanduser()

    def _export_text(self) -> str:
        return (
            "UniScribe — resumo da aula\n"
            "=========================\n\n"
            f"{self._summary_text.strip()}\n"
        )

    def export_summary(self, *args: Any) -> Optional[Path]:
        del args
        if not self._summary_text:
            self._set_notice("Não há resumo para exportar ainda.")
            return None
        try:
            directory = self._export_directory()
            directory.mkdir(parents=True, exist_ok=True)
            filename = time.strftime("uniscribe-summary-%Y%m%d-%H%M%S.txt", time.localtime())
            destination = directory / filename
            # Avoid silently replacing a file when two exports happen in the
            # same second, while keeping the filename user-friendly.
            suffix = 1
            while destination.exists():
                stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
                destination = directory / f"uniscribe-summary-{stamp}-{suffix}.txt"
                suffix += 1
            destination.write_text(self._export_text(), encoding="utf-8")
        except Exception as error:
            self._set_notice(f"Não foi possível exportar .txt: {_safe_error_detail(error)}")
            return None
        self.last_export_path = destination
        self._set_notice(f"Arquivo salvo: {destination}")
        return destination

    def shutdown(self) -> None:
        """Best-effort cleanup when the host application exits."""

        if self._processing_event is not None:
            for target in (self._processing_event, self._process_recording):
                try:
                    self._clock.unschedule(target)
                except Exception:
                    pass
            self._processing_event = None
        if self.state == STATE_LISTENING:
            try:
                self._recorder_call("stop")
            except Exception:
                pass
            self._set_state(STATE_IDLE)
        elif self.state == STATE_PROCESSING:
            self._set_state(STATE_IDLE)
        self._active_audio_path = None

    def on_pre_exit(self, *args: Any) -> None:
        del args
        self.shutdown()


# Compatibility aliases used by a few older screen integrations.
Home = HomeScreen
SummaryScreen = HomeScreen

__all__ = [
    "STATE_ERROR",
    "STATE_IDLE",
    "STATE_LISTENING",
    "STATE_PROCESSING",
    "STATE_READY",
    "FlowError",
    "Home",
    "HomeScreen",
    "OfflineError",
    "SummaryScreen",
]
