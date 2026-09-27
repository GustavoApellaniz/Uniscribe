from uniscribe.ui import SimpleScreen


class NotesScreen(SimpleScreen):
    def __init__(self, **kwargs) -> None:
        super().__init__(heading="Notas", **kwargs)
