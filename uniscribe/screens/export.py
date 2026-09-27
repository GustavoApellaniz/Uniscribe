from uniscribe.ui import SimpleScreen


class ExportScreen(SimpleScreen):
    def __init__(self, **kwargs) -> None:
        super().__init__(heading="Exportar", **kwargs)
