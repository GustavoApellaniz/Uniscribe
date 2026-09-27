from uniscribe.ui import SimpleScreen


class TranscriptionScreen(SimpleScreen):
    def __init__(self, **kwargs) -> None:
        super().__init__(heading="Transcrição", **kwargs)
