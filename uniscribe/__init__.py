__all__ = ["UniScribeApp"]


def __getattr__(name: str):
    if name == "UniScribeApp":
        from uniscribe.app import UniScribeApp

        return UniScribeApp
    raise AttributeError(name)
