"""Plain-text export for lecture summaries."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from uniscribe.domain.models import Summary, Transcript


def _section(title: str, values: Iterable[str]) -> list[str]:
    items = [str(value).strip() for value in values if str(value).strip()]
    if not items:
        return []
    return [f"{title}:", *[f"- {item}" for item in items], ""]


def summary_to_text(summary: Summary, transcript: Transcript | None = None) -> str:
    """Render a summary as UTF-8-friendly plain text.

    Only data already present in the domain object is rendered.  The optional
    transcript is included for auditability and is not sent to a provider.
    """

    title = summary.title.strip() or f"Aula {summary.lecture_id}"
    lines = [title, "=" * len(title), ""]
    if summary.final_summary.strip():
        lines.extend(["Resumo final", "------------", summary.final_summary.strip(), ""])
    if summary.bullets:
        lines.extend(_section("Pontos principais", summary.bullets))
    lines.extend(_section("Conceitos principais", summary.key_concepts))
    lines.extend(_section("Definições", summary.definitions))
    lines.extend(_section("Explicações", summary.explanations))
    lines.extend(_section("Exemplos", summary.examples))
    lines.extend(_section("Fórmulas", summary.formulas))
    lines.extend(_section("Pontos importantes", summary.important_points))
    lines.extend(_section("Dúvidas detectadas", summary.detected_questions))
    lines.extend(_section("Incertezas", summary.uncertainties))
    if transcript is not None:
        lines.extend(_section("Transcrição filtrada", [transcript.relevant_text]))
    return "\n".join(lines).rstrip() + "\n"


def export_summary_txt(
    summary: Summary,
    destination: Path | str,
    transcript: Transcript | None = None,
) -> Path:
    """Write ``summary`` as UTF-8 and return the resulting path."""

    target = Path(destination).expanduser()
    if target.is_dir() or not target.suffix:
        target = target / f"lecture_{summary.lecture_id}.txt"
    if target.suffix.lower() != ".txt":
        target = target.with_suffix(".txt")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(summary_to_text(summary, transcript), encoding="utf-8")
    return target


__all__ = ["export_summary_txt", "summary_to_text"]
