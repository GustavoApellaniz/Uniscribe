from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen


class SimpleScreen(Screen):
    def __init__(self, heading: str, **kwargs) -> None:
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=24, spacing=12)
        layout.add_widget(Label(text=heading, font_size="22sp"))
        back = Button(text="Voltar", size_hint_y=None, height=48)
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "home"))
        layout.add_widget(back)
        self.add_widget(layout)
