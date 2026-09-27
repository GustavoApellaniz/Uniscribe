from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_android_multipart_prefix_has_audio_delimiter() -> None:
    source = (ROOT / "app/src/main/java/com/uniscribe/app/network/HttpTranscriptionService.kt").read_text()
    audio_section = source.split('append(multipartField(boundary, "language_tag", "pt-BR"))', 1)[1]
    assert 'append("--").append(boundary).append("\\r\\n")' in audio_section
    assert 'name=\\"audio\\"' in audio_section


def test_android_build_uses_one_kotlin_plugin_path() -> None:
    root = (ROOT / "build.gradle.kts").read_text()
    settings = (ROOT / "settings.gradle.kts").read_text()
    assert 'version "8.7.3"' in root
    assert "resolutionStrategy" not in settings
