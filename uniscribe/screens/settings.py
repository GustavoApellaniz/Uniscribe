from uniscribe.ui import SimpleScreen


class SettingsScreen(SimpleScreen):
    def __init__(self, **kwargs) -> None:
        super().__init__(heading="Ajustes", **kwargs)
