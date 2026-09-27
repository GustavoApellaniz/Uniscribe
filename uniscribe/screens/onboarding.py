from uniscribe.ui import SimpleScreen


class OnboardingScreen(SimpleScreen):
    def __init__(self, **kwargs) -> None:
        super().__init__(heading="Bem-vindo ao UniScribe", **kwargs)
