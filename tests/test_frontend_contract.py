from pathlib import Path


def test_frontend_does_not_inject_transcript_html() -> None:
    source = (Path(__file__).parents[1] / "frontend" / "app.js").read_text()
    assert "innerHTML" not in source
    assert "renderTextList" in source
    assert "normaliseBackendUrl" in source


def test_frontend_declares_mvp_actions() -> None:
    html = (Path(__file__).parents[1] / "frontend" / "index.html").read_text()
    for marker in ("Start Listening", "Stop", "Processing...", "Copy", "Export .txt"):
        assert marker in html
