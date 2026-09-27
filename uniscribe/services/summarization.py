"""Deterministic, extractive summarisation for a safe local fallback.

The fallback never asks a language model to fill gaps.  It selects complete
source sentences using fixed rules, so facts, negations, and uncertainty
wording come directly from the transcript.  In particular, hedges such as
``talvez`` and ``não sei`` are detected, retained, and exposed in
``SummaryResult.uncertainties``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Protocol, Sequence


# Sentence boundaries require whitespace after punctuation.  This avoids
# splitting decimal numbers such as ``3.14`` while staying deliberately
# conservative about what counts as a sentence.
_SENTENCE_PATTERN = re.compile(r".*?(?:[.!?…]+(?=\s|$)|$)", re.DOTALL)

# These are markers, not replacements.  The original sentence is always
# returned unchanged apart from insignificant whitespace normalisation.
_UNCERTAINTY_PATTERN = re.compile(
    r"\b(?:"
    r"talvez|acho\s+que|parece(?:m)?|pod(?:e|eriam|eria)|"
    r"provavelmente|possivelmente|aparentemente|"
    r"n[aã]o\s+(?:sei|tenho\s+certeza)|n[aã]o\s+est[aá]\s+claro|"
    r"incerto|incerteza|inaud[íi]vel|desconhe[çc]o|"
    r"perhaps|maybe|might|may|not\s+sure|uncertain|unclear"
    r")\b",
    re.IGNORECASE,
)

_DEFINITION_CUES = (
    "defin",
    "conceito",
    "significa",
    "quer dizer",
    "caracteriza",
)
_EXAMPLE_CUES = ("exemplo", "por exemplo", "caso", "isto é", "assim")
_IMPORTANCE_CUES = (
    "importante",
    "essencial",
    "principal",
    "atenção",
    "atencao",
    "lembre",
    "prova",
    "exame",
)
_FORMULA_CUES = ("fórmula", "formula", "equação", "equacao", "=", "teorema")
_QUESTION_CUES = ("?", "dúvida", "duvida", "pergunta")
_CLOSURE_CUES = ("conclusão", "conclusao", "portanto", "logo", "finalmente")


class SummarizationError(RuntimeError):
    """Base class for summarisation errors."""


@dataclass
class SummaryResult:
    """Extractive summary plus its provenance and uncertainty metadata.

    ``text`` is the convenient string form used by text consumers.  The
    result remains a distinct object so the application layer can retain
    ``bullets`` and ``uncertainties`` instead of flattening them into prose.
    """

    bullets: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    source_sentences: list[str] = field(default_factory=list)
    used_fallback: bool = True

    def __post_init__(self) -> None:
        self.bullets = [
            str(bullet).strip() for bullet in self.bullets if str(bullet).strip()
        ]
        self.uncertainties = [
            str(sentence).strip()
            for sentence in self.uncertainties
            if str(sentence).strip()
        ]
        self.source_sentences = [
            str(sentence).strip()
            for sentence in self.source_sentences
            if str(sentence).strip()
        ]
        self.used_fallback = bool(self.used_fallback)

    @property
    def text(self) -> str:
        """The bullet-formatted summary text."""

        return "\n".join(f"- {bullet}" for bullet in self.bullets)

    @property
    def summary(self) -> str:
        """Alias for :attr:`text`."""

        return self.text

    @property
    def is_fallback(self) -> bool:
        return self.used_fallback

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation."""

        return {
            "summary": self.text,
            "bullets": list(self.bullets),
            "uncertainties": list(self.uncertainties),
            "source_sentences": list(self.source_sentences),
            "used_fallback": self.used_fallback,
        }

    # Small conveniences make the result pleasant to use with either a text
    # consumer or a caller expecting an extractive sequence.
    def __str__(self) -> str:
        return self.text

    def __contains__(self, value: object) -> bool:
        return str(value) in self.text

    def __iter__(self):
        return iter(self.bullets)

    def __getitem__(self, key):
        return self.bullets[key]

    def __bool__(self) -> bool:
        return bool(self.bullets)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.text == other
        if isinstance(other, SummaryResult):
            return (
                self.bullets == other.bullets
                and self.uncertainties == other.uncertainties
                and self.source_sentences == other.source_sentences
                and self.used_fallback == other.used_fallback
            )
        if isinstance(other, (list, tuple)):
            return self.bullets == list(other)
        return NotImplemented


class Summarizer(Protocol):
    """Interface accepted by :class:`SummarizationService`."""

    def summarize(self, transcript: str) -> SummaryResult:
        """Return a summary for ``transcript``."""


def _normalise_whitespace(value: str) -> str:
    """Collapse formatting whitespace without changing words or punctuation."""

    return " ".join(value.split())


def extract_sentences(transcript: str) -> list[str]:
    """Split a transcript into conservative, non-empty source sentences."""

    if not isinstance(transcript, str):
        raise TypeError("transcript must be a string")
    normalised = _normalise_whitespace(transcript)
    if not normalised:
        return []
    return [
        match.group(0).strip()
        for match in _SENTENCE_PATTERN.finditer(normalised)
        if match.group(0).strip()
    ]


def is_uncertain(sentence: str) -> bool:
    """Return whether ``sentence`` contains an explicit uncertainty marker."""

    return bool(_UNCERTAINTY_PATTERN.search(sentence))


def _score_sentence(sentence: str, index: int) -> tuple[int, int, int]:
    """Return a stable importance score for one sentence."""

    lowered = sentence.casefold()
    score = 0
    if is_uncertain(sentence):
        # Uncertainty is protected before ordinary importance heuristics.
        score += 100
    if any(cue in lowered for cue in _DEFINITION_CUES):
        score += 8
    if any(cue in lowered for cue in _EXAMPLE_CUES):
        score += 6
    if any(cue in lowered for cue in _IMPORTANCE_CUES):
        score += 7
    if any(cue in lowered for cue in _FORMULA_CUES):
        score += 5
    if any(cue in lowered for cue in _QUESTION_CUES):
        score += 3
    if any(cue in lowered for cue in _CLOSURE_CUES):
        score += 4
    # A small, bounded length preference avoids selecting only fragments
    # without rewarding arbitrary repetition.
    score += min(len(sentence) // 80, 3)
    # Earlier sentences win ties, making output independent of hash/set order.
    return score, -index, index


def _select_sentences(sentences: Sequence[str], max_sentences: int) -> list[str]:
    """Select source sentences while prioritising all explicit uncertainty."""

    if max_sentences < 0:
        raise ValueError("max_sentences must be greater than or equal to zero")
    if len(sentences) <= max_sentences:
        return list(sentences)
    if max_sentences == 0:
        return []

    uncertain = [sentence for sentence in sentences if is_uncertain(sentence)]
    # Protect explicit hedges first.  If there are more hedges than the hard
    # limit, the earliest ones are retained; all detected hedges remain in the
    # result metadata so a caller can choose a larger limit.
    if len(uncertain) >= max_sentences:
        uncertain_indices = [
            index for index, sentence in enumerate(sentences) if is_uncertain(sentence)
        ]
        selected_indices = set(uncertain_indices[:max_sentences])
    else:
        ranked = sorted(
            (
                (index, _score_sentence(sentence, index))
                for index, sentence in enumerate(sentences)
                if not is_uncertain(sentence)
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        selected_indices = {index for index, _ in ranked[: max_sentences - len(uncertain)]}
        selected_indices.update(
            index for index, sentence in enumerate(sentences) if is_uncertain(sentence)
        )

    return [sentence for index, sentence in enumerate(sentences) if index in selected_indices]


class DeterministicSummarizer:
    """A deterministic extractive summariser suitable for offline fallback."""

    def __init__(self, *, max_sentences: int = 8) -> None:
        if not isinstance(max_sentences, int) or isinstance(max_sentences, bool):
            raise TypeError("max_sentences must be an integer")
        if max_sentences < 0:
            raise ValueError("max_sentences must be greater than or equal to zero")
        self.max_sentences = max_sentences

    def summarize(self, transcript: str) -> SummaryResult:
        """Select source sentences without generating or resolving facts."""

        sentences = extract_sentences(transcript)
        selected = _select_sentences(sentences, self.max_sentences)
        uncertainties = [sentence for sentence in sentences if is_uncertain(sentence)]
        return SummaryResult(
            selected,
            uncertainties=uncertainties,
            source_sentences=sentences,
            used_fallback=True,
        )

    def summarize_text(self, transcript: str) -> str:
        """Return only the bullet-formatted text."""

        return self.summarize(transcript).text


# Descriptive aliases for applications that call this a local/fallback
# summariser rather than an extractive one.  ``FallbackSummarizer`` itself is
# defined below as the service that can wrap an optional primary backend.
LocalSummarizer = DeterministicSummarizer
DeterministicFallbackSummarizer = DeterministicSummarizer
DeterministicSummary = DeterministicSummarizer
ExtractiveSummarizer = DeterministicSummarizer


def _coerce_summary_result(
    value: Any, *, used_fallback: bool = False
) -> SummaryResult:
    """Convert an injected summariser's result without adding information."""

    if isinstance(value, SummaryResult):
        return SummaryResult(
            value.bullets,
            uncertainties=value.uncertainties,
            source_sentences=value.source_sentences,
            used_fallback=used_fallback,
        )
    if isinstance(value, str):
        text = _normalise_whitespace(value)
        return SummaryResult(
            [text] if text else [],
            uncertainties=[text] if text and is_uncertain(text) else [],
            source_sentences=[text] if text else [],
            used_fallback=used_fallback,
        )
    if isinstance(value, Mapping):
        # Accept common structured-summary field names without interpreting or
        # rewriting their contents.  Unknown mappings are rejected rather than
        # serialised into a misleading summary.
        candidates: list[str] = []
        for key in ("summary", "resumo", "final_summary", "key_points", "principais"):
            field = value.get(key)
            if isinstance(field, str) and field.strip():
                candidates.append(field.strip())
            elif isinstance(field, Sequence) and not isinstance(field, (str, bytes)):
                candidates.extend(
                    item.strip() for item in field if isinstance(item, str) and item.strip()
                )
        if not candidates:
            raise SummarizationError(
                "A structured summariser result must contain summary or key_points"
            )
        return SummaryResult(
            candidates,
            uncertainties=[item for item in candidates if is_uncertain(item)],
            source_sentences=candidates,
            used_fallback=used_fallback,
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        bullets = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if all(isinstance(item, str) for item in value):
            return SummaryResult(
                bullets,
                uncertainties=[item for item in bullets if is_uncertain(item)],
                source_sentences=bullets,
                used_fallback=used_fallback,
            )
    raise SummarizationError(
        "Summariser must return SummaryResult, text, or a sequence of strings"
    )


class SummarizationService:
    """Use an injected primary summariser with a deterministic local fallback.

    The primary is called through dependency injection.  Any ordinary
    exception (or a caller-selected exception tuple) causes the deterministic
    fallback to run; ``KeyboardInterrupt`` and ``SystemExit`` are not swallowed.
    """

    def __init__(
        self,
        primary: Optional[Any] = None,
        *,
        fallback: Optional[Any] = None,
        fallback_on: tuple[type[BaseException], ...] = (Exception,),
    ) -> None:
        if primary is not None and not (
            callable(primary) or callable(getattr(primary, "summarize", None))
        ):
            raise TypeError("primary must provide summarize() or be callable")
        if fallback is not None and not (
            callable(fallback) or callable(getattr(fallback, "summarize", None))
        ):
            raise TypeError("fallback must provide summarize() or be callable")
        if not isinstance(fallback_on, tuple) or not all(
            issubclass(item, BaseException) for item in fallback_on
        ):
            raise TypeError("fallback_on must be a tuple of exception classes")
        self.primary = primary
        self.fallback = fallback if fallback is not None else DeterministicSummarizer()
        self.fallback_on = fallback_on

    @staticmethod
    def _invoke(summariser: Any, transcript: str) -> Any:
        method = getattr(summariser, "summarize", None)
        return method(transcript) if callable(method) else summariser(transcript)

    def summarize(self, transcript: str) -> SummaryResult:
        if not isinstance(transcript, str):
            raise TypeError("transcript must be a string")
        if self.primary is not None:
            try:
                result = self._invoke(self.primary, transcript)
                return _coerce_summary_result(result, used_fallback=False)
            except self.fallback_on:
                pass
        result = self._invoke(self.fallback, transcript)
        return _coerce_summary_result(result, used_fallback=True)

    def summarize_text(self, transcript: str) -> str:
        return self.summarize(transcript).text


class FallbackSummarizer(SummarizationService):
    """Named façade for a primary summariser plus deterministic fallback."""

    def __init__(
        self,
        primary: Optional[Any] = None,
        *,
        fallback: Optional[Any] = None,
        fallback_on: tuple[type[BaseException], ...] = (Exception,),
        max_sentences: Optional[int] = None,
    ) -> None:
        if max_sentences is not None:
            if fallback is not None:
                raise TypeError("provide either fallback or max_sentences, not both")
            fallback = DeterministicSummarizer(max_sentences=max_sentences)
        super().__init__(primary, fallback=fallback, fallback_on=fallback_on)


# Aliases that make the same dependency-injected service easy to discover.
SummaryService = SummarizationService
LocalFallbackSummarizer = FallbackSummarizer


def summarize_transcript(transcript: str, *, max_sentences: int = 8) -> SummaryResult:
    """Summarise a transcript with the deterministic local implementation."""

    return DeterministicSummarizer(max_sentences=max_sentences).summarize(transcript)


def summarize(transcript: str, *, max_sentences: int = 8) -> SummaryResult:
    """Short alias for :func:`summarize_transcript`."""

    return summarize_transcript(transcript, max_sentences=max_sentences)


def summary_text(transcript: str, *, max_sentences: int = 8) -> str:
    """Return the deterministic summary as plain text."""

    return summarize_transcript(transcript, max_sentences=max_sentences).text


# Alternate word order used by some callers.
summarize_text = summary_text


__all__ = [
    "DeterministicFallbackSummarizer",
    "DeterministicSummarizer",
    "DeterministicSummary",
    "ExtractiveSummarizer",
    "FallbackSummarizer",
    "LocalFallbackSummarizer",
    "LocalSummarizer",
    "SummarizationError",
    "SummarizationService",
    "Summarizer",
    "SummaryResult",
    "SummaryService",
    "extract_sentences",
    "is_uncertain",
    "summarize",
    "summarize_transcript",
    "summarize_text",
    "summary_text",
]
