from uniscribe.ui import SimpleScreen


class SummariesScreen(SimpleScreen):
    def __init__(self, **kwargs) -> None:
        super().__init__(heading="Resumos", **kwargs)
