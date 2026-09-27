from uniscribe.ui import SimpleScreen


class LecturesScreen(SimpleScreen):
    def __init__(self, **kwargs) -> None:
        super().__init__(heading="Aulas", **kwargs)
