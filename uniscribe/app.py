"""Kivy application wiring for the UniScribe MVP."""

from __future__ import annotations

from typing import Any

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager

from uniscribe.screens.courses import CoursesScreen
from uniscribe.screens.export import ExportScreen
from uniscribe.screens.home import HomeScreen
from uniscribe.screens.lectures import LecturesScreen
from uniscribe.screens.notes import NotesScreen
from uniscribe.screens.onboarding import OnboardingScreen
from uniscribe.screens.recorder import RecorderScreen
from uniscribe.screens.summaries import SummariesScreen
from uniscribe.screens.search import SearchScreen
from uniscribe.screens.settings import SettingsScreen
from uniscribe.screens.subscription import SubscriptionScreen
from uniscribe.screens.transcription import TranscriptionScreen


class UniScribeApp(App):
    """Application root with injectable MVP services.

    No concrete remote backend is selected here.  Callers embedding the app
    can inject local or test implementations; the defaults are resolved by
    :class:`HomeScreen` and remain offline-safe.
    """

    title = "UniScribe"

    def __init__(
        self,
        *,
        recorder: Any = None,
        transcriber: Any = None,
        summariser: Any = None,
        permission_checker: Any = None,
        network_checker: Any = None,
        require_internet: bool = False,
        export_dir: Any = None,
        clipboard: Any = None,
        **kwargs: Any,
    ) -> None:
        # Accept both spellings at the application boundary while keeping the
        # Kivy App constructor free of service-specific keyword arguments.
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
        self._recorder = recorder
        self._transcriber = transcriber
        self._summariser = summariser
        self._permission_checker = permission_checker
        self._network_checker = network_checker
        self._require_internet = bool(require_internet)
        self._export_dir = export_dir
        self._clipboard = clipboard
        self.home_screen: HomeScreen | None = None
        self.screen_manager: ScreenManager | None = None

    def build(self) -> ScreenManager:
        manager = ScreenManager()
        self.screen_manager = manager

        # Home is the MVP's single visible flow.  The remaining screens stay
        # registered so existing navigation integrations remain compatible.
        home = HomeScreen(
            name="home",
            recorder=self._recorder,
            transcriber=self._transcriber,
            summariser=self._summariser,
            permission_checker=self._permission_checker,
            network_checker=self._network_checker,
            require_internet=self._require_internet,
            export_dir=self._export_dir,
            clipboard=self._clipboard,
        )
        self.home_screen = home
        screens = (
            OnboardingScreen(name="onboarding"),
            home,
            CoursesScreen(name="courses"),
            LecturesScreen(name="lectures"),
            RecorderScreen(name="recorder"),
            TranscriptionScreen(name="transcription"),
            NotesScreen(name="notes"),
            SummariesScreen(name="summaries"),
            ExportScreen(name="export"),
            SearchScreen(name="search"),
            SettingsScreen(name="settings"),
            SubscriptionScreen(name="subscription"),
        )
        for screen in screens:
            manager.add_widget(screen)
        manager.current = "home"
        return manager

    def on_stop(self) -> None:
        """Release an active recording when Kivy stops the application."""

        if self.home_screen is not None:
            self.home_screen.shutdown()


__all__ = ["UniScribeApp"]
