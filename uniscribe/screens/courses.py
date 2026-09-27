from uniscribe.ui import SimpleScreen


class CoursesScreen(SimpleScreen):
    def __init__(self, **kwargs) -> None:
        super().__init__(heading="Cursos", **kwargs)
