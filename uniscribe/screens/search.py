from uniscribe.ui import SimpleScreen


class SearchScreen(SimpleScreen):
    def __init__(self, **kwargs) -> None:
        super().__init__(heading="Buscar", **kwargs)
