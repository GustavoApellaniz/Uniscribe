"""Compatibility screen for the original recorder route.

The MVP flow lives on :class:`~uniscribe.screens.home.HomeScreen`.  This
screen remains registered for older navigation integrations, but it now
fails visibly and safely instead of allowing recorder/storage errors to escape.
"""

from pathlib import Path
from typing import Any

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen

try:
    from uniscribe.domain.usecases import StartLectureRecording
except Exception:  # The legacy screen can still be imported without a backend.
    StartLectureRecording = None  # type: ignore[assignment]

try:
    from uniscribe.services.audio import AudioRecorder
except Exception:
    AudioRecorder = None  # type: ignore[assignment,misc]


class RecorderScreen(Screen):
    """Legacy recorder screen with defensive error handling."""

    def __init__(self, recorder: Any = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if recorder is None and AudioRecorder is not None:
            try:
                recorder = AudioRecorder(Path.home() / ".uniscribe" / "lectures")
            except Exception as error:
                recorder = None
                self._initialisation_error = str(error)
        elif recorder is None:
            self._initialisation_error = "Audio service is unavailable"
        else:
            self._initialisation_error = ""
        self._recorder = recorder
        self._lecture: Any = None
        self._status = Label(text="Pronto para gravar")

        layout = BoxLayout(orientation="vertical", padding=24, spacing=12)
        layout.add_widget(Label(text="Gravar aula", font_size="22sp"))
        layout.add_widget(self._status)

        start = Button(text="Iniciar", size_hint_y=None, height=48)
        start.bind(on_press=self._start)
        stop = Button(text="Parar", size_hint_y=None, height=48)
        stop.bind(on_press=self._stop)
        back = Button(text="Voltar", size_hint_y=None, height=48)
        back.bind(on_press=self._go_home)
        layout.add_widget(start)
        layout.add_widget(stop)
        layout.add_widget(back)
        self.add_widget(layout)

        if self._recorder is None:
            self._status.text = "Gravador indisponível neste dispositivo"

    def _start(self, *_args: Any) -> bool:
        if self._recorder is None or StartLectureRecording is None:
            self._status.text = "Não foi possível iniciar o gravador"
            return False
        if self._lecture is not None:
            self._status.text = "Já existe uma gravação em andamento"
            return False
        try:
            self._lecture = StartLectureRecording(self._recorder)(
                course_id="default",
                title="Nova aula",
            )
        except Exception as error:
            self._status.text = f"Erro ao iniciar: {error}"
            return False
        self._status.text = f"Gravando: {self._lecture.audio_path}"
        return True

    def _stop(self, *_args: Any) -> bool:
        if self._recorder is None or self._lecture is None:
            self._status.text = "Nada para parar"
            return False
        try:
            path = self._recorder.stop()
        except Exception as error:
            self._status.text = f"Erro ao parar: {error}"
            return False
        if path is None:
            self._status.text = "Nada para parar"
            return False
        self._status.text = f"Salvo: {path}"
        self._lecture = None
        if self.manager is not None:
            self.manager.current = "transcription"
        return True

    def _go_home(self, *_args: Any) -> None:
        if self.manager is not None:
            self.manager.current = "home"


__all__ = ["RecorderScreen"]
