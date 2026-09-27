"""Limpeza determinística e sem dependências para transcrições.

O filtro deste módulo é deliberadamente conservador.  Ele remove apenas
marcas de silêncio, preenchimentos claramente discursivos e repetições
lexicais imediatas.  Não tenta inferir topicalidade, corrigir gramática ou
reescrever o conteúdo da aula.  Assim, perguntas, definições, exemplos,
datas, valores, fórmulas e marcadores de incerteza permanecem disponíveis
para as etapas seguintes do pipeline.

A API principal é :func:`filter_transcript`, que devolve texto simples.
Usuários que precisarem de auditoria podem usar ``TranscriptFilter.process``
ou ``filter_transcript_result`` para receber um :class:`FilterResult` com os
itens removidos.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Final


# Palavras curtas e de baixa informação semântica.  ``um``/``uma`` e
# ``então``/``aí`` são tratados de forma contextual (ver _is_isolated_span),
# pois também podem ter significado gramatical ou referencial.
DEFAULT_FILLER_WORDS: Final[frozenset[str]] = frozenset(
    {
        "ah",
        "aha",
        "ahh",
        "eh",
        "hm",
        "hmm",
        "hum",
        "uh",
        "uhm",
        "um",
        "uma",
        "né",
        "ne",
        "tipo",
        "aí",
        "ai",
        "então",
        "entao",
        "tá",
        "ta",
        "tão",
        "tao",
        "sabe",
        "ok",
        "okay",
        "like",
        "so",
        "well",
    }
)

# Frases têm prioridade sobre palavras individuais.  A implementação ainda
# exige que a frase esteja isolada por pontuação/fronteira, para não apagar
# uma expressão que faz parte de uma frase ou de uma definição.
DEFAULT_FILLER_PHRASES: Final[frozenset[str]] = frozenset(
    {
        "tipo assim",
        "sei lá",
        "sei la",
        "you know",
        "i mean",
        "kind of",
        "por assim dizer",
    }
)

# Números escritos por extenso são protegidos quando aparecem ao lado de
# "um"/"uma", para não transformar uma enumeração em uma lista deslocada.
_NUMBER_WORDS: Final[frozenset[str]] = frozenset(
    {
        "zero",
        "um",
        "uma",
        "dois",
        "duas",
        "tres",
        "três",
        "quatro",
        "cinco",
        "seis",
        "sete",
        "oito",
        "nove",
        "dez",
        "onze",
        "doze",
        "treze",
        "quatorze",
        "quinze",
        "dezesseis",
        "dezessete",
        "dezoito",
        "dezenove",
        "vinte",
        "trinta",
        "quarenta",
        "cinquenta",
        "sessenta",
        "setenta",
        "oitenta",
        "noventa",
        "cem",
        "mil",
        "milhao",
        "milhão",
        "primeiro",
        "primeira",
        "segundo",
        "segunda",
        "terceiro",
        "terceira",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "hundred",
        "thousand",
        "first",
        "second",
        "third",
    }
)

# Para repetições, preservamos números escritos por extenso; artigos ainda
# podem ser removidos quando aparecem como fillers.
_NON_ARTICLE_NUMBER_WORDS: Final[frozenset[str]] = frozenset(
    _NUMBER_WORDS - {"um", "uma"}
)

# Os itens são rótulos, não marcas completas.  A função remove, por exemplo,
# ``[silêncio]``, ``(pause)`` e ``<|blank_audio|>`` usando esta lista.
DEFAULT_SILENCE_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "silêncio",
        "silencio",
        "silence",
        "silent",
        "pausa",
        "pause",
        "blank audio",
        "blank_audio",
        "áudio em branco",
        "audio em branco",
        "sem áudio",
        "sem audio",
        "no audio",
        "no sound",
        "sil",
        "sil.",
        "noise",
        "ruído",
        "ruido",
    }
)

# Fillers que, mesmo sem pontuação, são quase sempre ruído de transcrição.
# Os demais candidatos são removidos somente quando são realmente isolados.
_UNAMBIGUOUS_FILLERS: Final[frozenset[str]] = frozenset(
    {
        "ah",
        "aha",
        "ahh",
        "eh",
        "hm",
        "hmm",
        "hum",
        "uh",
        "uhm",
        "né",
        "ne",
        "sei lá",
        "sei la",
    }
)

_SILENCE_MODIFIERS: Final[frozenset[str]] = frozenset(
    {
        "longa",
        "longo",
        "long",
        "curta",
        "curto",
        "short",
        "prolongada",
        "prolongado",
        "silenciosa",
        "silencioso",
    }
)

_REPETITION_FUNCTION_WORDS: Final[frozenset[str]] = frozenset(
    {
        "a",
        "as",
        "o",
        "os",
        "um",
        "uma",
        "uns",
        "umas",
        "de",
        "da",
        "do",
        "das",
        "dos",
        "e",
        "ou",
        "que",
        "para",
        "por",
        "com",
        "sem",
        "the",
        "an",
        "of",
        "to",
        "and",
        "or",
    }
)

_WORD_RE: Final[re.Pattern[str]] = re.compile(
    r"[^\W\d_]+(?:[-'’][^\W_]+)*", re.UNICODE
)
# Inclui números para que "um 2" não seja considerado um filler isolado.
_LEXICAL_RE: Final[re.Pattern[str]] = re.compile(
    r"[^\W_]+(?:[-'’][^\W_]+)*", re.UNICODE
)

# Qualquer wrapper é identificado primeiro; o conteúdo é validado pelo
# rótulo depois.  Isso permite reconhecer acentos e também marcadores
#[<|silence|>] sem uma lista enorme de formas.
_WRAPPED_SILENCE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w])(?P<token>"
    r"\[\s*\[?[^\]\n]{1,80}?\]?\s*\]"
    r"|\(\s*[^\)\n]{1,80}?\s*\)"
    r"|\{\s*[^\}\n]{1,80}?\s*\}"
    r"|【\s*[^】\n]{1,80}?\s*】"
    r"|<\|[^\|\n]{1,80}?\|>"
    r"|<\s*[^>\n]{1,80}?\s*>"
    r")(?!\w)",
    re.IGNORECASE | re.UNICODE,
)

# Marcadores de incerteza são protegidos das operações de repetição/filler.
_UNCERTAINTY_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w])(?:"
    r"\[[^\]\n]{0,100}(?:\?{1,}|\.{3,}|…|"
    r"incert(?:o|a|ez)|inaud(?:ível|ivel|ible)|unclear|unsure|"
    r"n[aã]o (?:sei|claro|tenho certeza)|unknown|uncertain)[^\]\n]{0,100}\]"
    r"|\([^)\n]{0,100}(?:\?{1,}|\.{3,}|…|"
    r"incert(?:o|a|ez)|inaud(?:ível|ivel|ible)|unclear|unsure|"
    r"n[aã]o (?:sei|claro|tenho certeza)|unknown|uncertain)[^)\n]{0,100}\)"
    r"|【[^】\n]{0,100}(?:\?{1,}|\.{3,}|…|"
    r"incert(?:o|a|ez)|inaud(?:ível|ivel|ible)|unclear|unsure|"
    r"n[aã]o (?:sei|claro|tenho certeza)|unknown|uncertain)[^】\n]{0,100}】"
    r"|<\|[^|\n]{0,100}(?:\?{1,}|\.{3,}|…|"
    r"incert(?:o|a|ez)|inaud(?:ível|ivel|ible)|unclear|unsure|"
    r"n[aã]o (?:sei|claro|tenho certeza)|unknown|uncertain)[^|\n]{0,100}\|>"
    r"|\b(?:acho\s+que|talvez|provavelmente|possivelmente|"
    r"não\s+tenho\s+certeza|n[aã]o\s+tenho\s+certeza|"
    r"maybe|perhaps|probably|i\s+think|not\s+sure)\b"
    r")(?![\w])",
    re.IGNORECASE | re.UNICODE,
)

_MATH_CONTEXT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<!\w)(?:[=+*/^%≤≥±√∑∫\\<>]|-\s|\s-)(?!\w)"
    r"|\d"
    r"|\([^()\n]*\)"
    r"|\{[^{}\n]*\}"
)

_HORIZONTAL_SPACE_RE: Final[re.Pattern[str]] = re.compile(r"[^\S\r\n]+")


@dataclass(frozen=True)
class _Word:
    """Trecho lexical com offsets para permitir edições não destrutivas."""

    start: int
    end: int
    text: str
    folded: str


@dataclass
class _RemovalLog:
    """Contadores temporários usados durante uma transformação."""

    fillers: list[str]
    repetitions: list[str]
    silence: list[str]


def _fold(value: str) -> str:
    """Normaliza caixa e acentos para comparações lexicais."""

    decomposed = unicodedata.normalize("NFD", value.casefold())
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(without_accents.split())


def _normalise_config_words(values: object) -> frozenset[str]:
    if values is None:
        return frozenset()
    if isinstance(values, str):
        values = (values,)
    try:
        iterator = iter(values)  # type: ignore[arg-type]
    except TypeError as error:
        raise TypeError("listas de fillers/silêncio devem ser iteráveis") from error
    return frozenset(
        folded
        for value in iterator
        if isinstance(value, str)
        for folded in (_fold(value),)
        if folded
    )


def _strip_marker_wrappers(value: str) -> str:
    value = value.strip()
    if value.startswith("<|") and value.endswith("|>"):
        return value[2:-2].strip()
    pairs = {"[": "]", "(": ")", "{": "}", "<": ">", "【": "】", "|": "|"}
    while len(value) >= 2 and value[0] in pairs:
        closing = pairs[value[0]]
        if not value.endswith(closing):
            break
        value = value[1:-1].strip()
    return value


@dataclass(frozen=True)
class FilterConfig:
    """Opções do filtro.

    As coleções são normalizadas para ``frozenset`` na inicialização, de modo
    que uma configuração possa ser reutilizada com segurança.  Os defaults
    são conservadores; aplicações podem substituir os conjuntos sem
    alterar o algoritmo.
    """

    filler_words: frozenset[str] | set[str] | tuple[str, ...] = DEFAULT_FILLER_WORDS
    filler_phrases: frozenset[str] | set[str] | tuple[str, ...] = DEFAULT_FILLER_PHRASES
    silence_tokens: frozenset[str] | set[str] | tuple[str, ...] = DEFAULT_SILENCE_TOKENS
    remove_fillers: bool = True
    remove_repetitions: bool = True
    remove_silence: bool = True
    normalize_whitespace: bool = True

    def __post_init__(self) -> None:
        words = _normalise_config_words(self.filler_words)
        phrases = _normalise_config_words(self.filler_phrases)
        # Aceitar uma frase no campo de palavras é conveniente e não muda a
        # semântica das opções existentes.
        phrase_candidates = {
            item for item in words if " " in item
        }
        words = frozenset(item for item in words if " " not in item)
        phrases = frozenset(phrases | phrase_candidates)
        silence = frozenset(
            _fold(_strip_marker_wrappers(item))
            for item in _normalise_config_words(self.silence_tokens)
            if _fold(_strip_marker_wrappers(item))
        )
        object.__setattr__(self, "filler_words", words)
        object.__setattr__(self, "filler_phrases", phrases)
        object.__setattr__(self, "silence_tokens", silence)


@dataclass(frozen=True)
class FilterResult:
    """Resultado auditável de uma operação de filtragem."""

    original_text: str
    filtered_text: str
    removed_fillers: tuple[str, ...] = ()
    removed_repetitions: tuple[str, ...] = ()
    removed_silence_tokens: tuple[str, ...] = ()

    @property
    def text(self) -> str:
        """Alias curto para integrations que chamam o resultado de ``text``."""

        return self.filtered_text

    @property
    def cleaned_text(self) -> str:
        """Alias legível para ``filtered_text``."""

        return self.filtered_text

    @property
    def output(self) -> str:
        """Alias de saída para integrações que chamam o texto de output."""

        return self.filtered_text

    @property
    def original(self) -> str:
        """Alias do texto de entrada original."""

        return self.original_text

    @property
    def removed_tokens(self) -> tuple[str, ...]:
        """Valores removidos agregados por categoria."""

        return (
            self.removed_fillers
            + self.removed_repetitions
            + self.removed_silence_tokens
        )

    @property
    def removed_filler_count(self) -> int:
        return len(self.removed_fillers)

    @property
    def removed_repetition_count(self) -> int:
        return len(self.removed_repetitions)

    @property
    def removed_silence_count(self) -> int:
        return len(self.removed_silence_tokens)

    @property
    def changed(self) -> bool:
        return self.original_text != self.filtered_text

    def as_dict(self) -> dict[str, object]:
        """Retorna uma representação simples e serializável do resultado."""

        return {
            "original_text": self.original_text,
            "filtered_text": self.filtered_text,
            "removed_fillers": list(self.removed_fillers),
            "removed_repetitions": list(self.removed_repetitions),
            "removed_silence_tokens": list(self.removed_silence_tokens),
        }

    def __str__(self) -> str:
        return self.filtered_text


def _coerce_text(value: str | None) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError("a transcrição deve ser str ou None")
    return value


def _is_silence_label(label: str, configured: frozenset[str]) -> bool:
    folded = _fold(label)
    if not folded:
        return False
    if folded in configured:
        return True
    for base in configured:
        if not folded.startswith(base + " "):
            continue
        remainder = folded[len(base) + 1 :].split()
        if remainder and all(word in _SILENCE_MODIFIERS for word in remainder):
            return True
    return False


def _protected_ranges(text: str) -> list[tuple[int, int]]:
    return [(match.start(), match.end()) for match in _UNCERTAINTY_RE.finditer(text)]


def _in_ranges(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start >= left and end <= right for left, right in ranges)


def _looks_like_math(text: str, start: int, end: int) -> bool:
    """Evita editar palavras que fazem parte de uma expressão numérica."""

    context = text[max(0, start - 12) : min(len(text), end + 12)]
    return bool(_MATH_CONTEXT_RE.search(context))


def _lexical_words(text: str) -> list[_Word]:
    return [
        _Word(match.start(), match.end(), match.group(0), _fold(match.group(0)))
        for match in _WORD_RE.finditer(text)
    ]


def _all_lexical_words(text: str) -> list[_Word]:
    return [
        _Word(match.start(), match.end(), match.group(0), _fold(match.group(0)))
        for match in _LEXICAL_RE.finditer(text)
    ]


def _has_non_alphanumeric_separator(separator: str) -> bool:
    # Espaço sozinho apenas une duas palavras; não as torna um filler
    # isolado.  Uma vírgula, travessão ou outro delimitador é que cria a
    # fronteira discurso-permissão usada acima.
    significant = separator.strip()
    return bool(significant) and any(
        not (character.isalnum() or character == "_") for character in significant
    )


def _is_isolated_span(
    text: str,
    start: int,
    end: int,
    words: list[_Word],
    first_index: int,
    last_index: int,
) -> bool:
    """Diz se o trecho está separado do resto por pontuação/fronteira.

    ``um exemplo`` e ``um 2`` não são fillers: os dois lados são vizinhos
    lexicais separados apenas por espaço.  Já ``um, exemplo`` tem um
    delimitador e pode ser um preenchimento discursivo.
    """

    if start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
        return False
    if end < len(text) and (text[end].isalnum() or text[end] == "_"):
        return False

    previous_word = words[first_index - 1] if first_index > 0 else None
    next_word = words[last_index + 1] if last_index + 1 < len(words) else None

    if previous_word is not None:
        separator = text[previous_word.end : start]
        if not _has_non_alphanumeric_separator(separator):
            return False
    if next_word is not None:
        separator = text[end : next_word.start]
        if not _has_non_alphanumeric_separator(separator):
            return False
    return True


def _is_bare_silence_isolated(
    text: str,
    start: int,
    end: int,
    words: list[_Word],
    first_index: int,
    last_index: int,
) -> bool:
    """Aceita bare tokens como anotação, sem remove-los de uma frase."""

    if not _is_isolated_span(text, start, end, words, first_index, last_index):
        return False
    previous_word = words[first_index - 1] if first_index > 0 else None
    next_word = words[last_index + 1] if last_index + 1 < len(words) else None
    separators = []
    if previous_word is not None:
        separators.append(text[previous_word.end : start])
    if next_word is not None:
        separators.append(text[end : next_word.start])
    # ``disse: silêncio.`` é conteúdo, enquanto ``[silêncio]``/``silêncio,``
    # é uma anotação.  Pontos de interrogação/exclamação também introduzem
    # conteúdo e por isso não autorizam a remoção de uma palavra nua.
    return not any(
        character in ":.?!" for separator in separators for character in separator
    )


def _silence_spans(line: str, configured: frozenset[str]) -> list[tuple[int, int, str]]:
    if not configured:
        return []
    found: list[tuple[int, int, str]] = []
    occupied: list[tuple[int, int]] = []

    for match in _WRAPPED_SILENCE_RE.finditer(line):
        token = match.group("token")
        inner = token
        if inner.startswith("[") and inner.endswith("]"):
            inner = inner[1:-1]
        elif inner.startswith("(") and inner.endswith(")"):
            inner = inner[1:-1]
        elif inner.startswith("{") and inner.endswith("}"):
            inner = inner[1:-1]
        elif inner.startswith("【") and inner.endswith("】"):
            inner = inner[1:-1]
        elif inner.startswith("<|") and inner.endswith("|>"):
            inner = inner[2:-2]
        elif inner.startswith("<") and inner.endswith(">"):
            inner = inner[1:-1]
        inner = _strip_marker_wrappers(inner.strip())
        if _is_silence_label(inner, configured):
            found.append((match.start(), match.end(), token))
            occupied.append((match.start(), match.end()))

    # Um token sem wrapper só é removido quando funciona como uma anotação
    # isolada.  Assim, "o silêncio é importante" permanece intacto.  O mesmo
    # caminho também aceita rótulos compostos, como ``blank audio``.
    lexical = _all_lexical_words(line)
    bare_candidates: list[tuple[int, int, str, int, int]] = []
    for index, word in enumerate(lexical):
        for base in sorted(configured, key=lambda item: (-len(item.split()), item)):
            parts = base.split()
            if index + len(parts) > len(lexical):
                continue
            block = lexical[index : index + len(parts)]
            if any(item.folded != part for item, part in zip(block, parts)):
                continue
            if any(
                line[block[position].end : block[position + 1].start].strip()
                for position in range(len(block) - 1)
            ):
                continue
            last_index = index + len(parts) - 1
            end_word = block[-1]
            if last_index + 1 < len(lexical):
                following = lexical[last_index + 1]
                if following.folded in _SILENCE_MODIFIERS:
                    last_index += 1
                    end_word = following
            bare_candidates.append(
                (
                    word.start,
                    end_word.end,
                    line[word.start : end_word.end],
                    index,
                    last_index,
                )
            )

    # Prefere a anotação mais longa quando há um rótulo composto e um
    # sobreposto; os marcadores já ocupados têm prioridade.
    for start, end, value, first_index, last_index in sorted(
        bare_candidates,
        key=lambda item: (item[0], -(item[1] - item[0])),
    ):
        if any(start < right and end > left for left, right in occupied):
            continue
        if not _is_bare_silence_isolated(
            line, start, end, lexical, first_index, last_index
        ):
            continue
        if _looks_like_math(line, start, end):
            continue
        found.append((start, end, value))
        occupied.append((start, end))

    found.sort(key=lambda item: item[0])
    return found


def _filler_candidates(
    line: str, config: FilterConfig
) -> list[tuple[int, int, str, int, int, bool]]:
    """Localiza phrases e palavras candidatas sem aplicar a edição."""

    # A mesma lista é usada para candidatos e para seus vizinhos.  Incluir
    # números é importante para não tratar ``um 2`` como um filler isolado.
    words = _all_lexical_words(line)
    candidates: list[tuple[int, int, str, int, int, bool]] = []
    used: list[tuple[int, int]] = []

    phrases = tuple(
        sorted(
            (phrase for phrase in config.filler_phrases if phrase),
            key=lambda phrase: (-len(phrase.split()), -len(phrase), phrase),
        )
    )
    for phrase in phrases:
        phrase_parts = phrase.split()
        if not phrase_parts or len(phrase_parts) > len(words):
            continue
        for start_index in range(len(words) - len(phrase_parts) + 1):
            indexes = range(start_index, start_index + len(phrase_parts))
            if any(words[index].folded != part for index, part in zip(indexes, phrase_parts)):
                continue
            # Phrases só podem conter whitespace entre suas palavras.
            if any(
                _WORD_RE.sub("", line[words[i].end : words[i + 1].start]).strip()
                for i in range(start_index, start_index + len(phrase_parts) - 1)
            ):
                continue
            end_index = start_index + len(phrase_parts) - 1
            start = words[start_index].start
            end = words[end_index].end
            if any(start < right and end > left for left, right in used):
                continue
            candidates.append(
                (
                    start,
                    end,
                    line[start:end],
                    start_index,
                    end_index,
                    _fold(line[start:end]) in _UNAMBIGUOUS_FILLERS,
                )
            )
            used.append((start, end))

    for index, word in enumerate(words):
        if word.folded not in config.filler_words:
            continue
        if any(word.start < right and word.end > left for left, right in used):
            continue
        candidates.append(
            (
                word.start,
                word.end,
                word.text,
                index,
                index,
                word.folded in _UNAMBIGUOUS_FILLERS,
            )
        )
        used.append((word.start, word.end))

    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    return candidates


def _expand_separator_deletion(text: str, start: int, end: int) -> tuple[int, int]:
    """Remove um separador de lista associado a uma anotação removida."""

    right = end
    while right < len(text) and text[right] in " \t":
        right += 1
    if right < len(text) and text[right] in ",;:-–—":
        return start, right + 1

    left = start
    while left > 0 and text[left - 1] in " \t":
        left -= 1
    if left > 0 and text[left - 1] in ",;:-–—":
        return left - 1, end
    return start, end


def _apply_deletions(
    text: str, deletions: list[tuple[int, int, str, str]]
) -> str:
    """Aplica deleções ordenadas, ignorando sobreposições."""

    if not deletions:
        return text
    pieces: list[str] = []
    cursor = 0
    for start, end, _value, _kind in sorted(deletions, key=lambda item: (item[0], item[1])):
        if start < cursor:
            continue
        pieces.append(text[cursor:start])
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def _remove_silence_from_line(
    line: str, config: FilterConfig, log: _RemovalLog
) -> str:
    if not config.remove_silence or not config.silence_tokens:
        return line
    spans = _silence_spans(line, config.silence_tokens)
    deletions = []
    for start, end, value in spans:
        deletion_start, deletion_end = _expand_separator_deletion(line, start, end)
        deletions.append((deletion_start, deletion_end, value, "silence"))
    for _start, _end, value, _kind in sorted(deletions, key=lambda item: item[0]):
        log.silence.append(value)
    return _apply_deletions(line, deletions)


def _remove_fillers_from_line(
    line: str, config: FilterConfig, log: _RemovalLog
) -> str:
    if not config.remove_fillers:
        return line
    protected = _protected_ranges(line)
    all_words = _all_lexical_words(line)
    deletions: list[tuple[int, int, str, str]] = []
    for start, end, value, first_index, last_index, unambiguous in _filler_candidates(
        line, config
    ):
        if _in_ranges(start, end, protected) or _looks_like_math(line, start, end):
            continue
        if not unambiguous:
            if not _is_isolated_span(
                line, start, end, all_words, first_index, last_index
            ):
                continue
            if _fold(value) in {"um", "uma"}:
                neighbors = []
                if first_index > 0:
                    neighbors.append(all_words[first_index - 1].folded)
                if last_index + 1 < len(all_words):
                    neighbors.append(all_words[last_index + 1].folded)
                if any(
                    neighbor in _NUMBER_WORDS and neighbor not in {"um", "uma"}
                    for neighbor in neighbors
                ):
                    continue
                # Preserve the article in constructions such as "uma, por
                # exemplo" and "um, como exemplo"; the marker is content,
                # not a hesitation.
                lookahead = [
                    word.folded
                    for word in all_words[last_index + 1 : last_index + 4]
                ]
                if "exemplo" in lookahead and any(
                    marker in lookahead[:2] for marker in {"por", "como"}
                ):
                    continue
        deletion_start, deletion_end = _expand_separator_deletion(line, start, end)
        deletions.append((deletion_start, deletion_end, value, "filler"))
    for _start, _end, value, _kind in sorted(deletions, key=lambda item: item[0]):
        log.fillers.append(value)
    return _apply_deletions(line, deletions)


def _repeat_separator(separator: str) -> bool:
    """Aceita apenas separadores triviais, nunca uma nova afirmação."""

    if not separator or any(character.isalnum() or character == "_" for character in separator):
        return False
    # ``...?`` e reticências são sinais de incerteza, não repetição
    # tautológica.  O ponto simples continua permitido entre frases.
    return not any(character in "?!…." for character in separator) or (
        separator.strip() == "."
    )


def _remove_single_repetitions_from_line(
    line: str, log: _RemovalLog
) -> str:
    words = _lexical_words(line)
    if len(words) < 2:
        return line
    protected = _protected_ranges(line)
    deletions: list[tuple[int, int, str, str]] = []
    index = 0
    while index < len(words) - 1:
        current = words[index]
        run_end = index + 1
        while run_end < len(words):
            following = words[run_end]
            if following.folded != current.folded:
                break
            if (
                current.folded in _NON_ARTICLE_NUMBER_WORDS
                or following.folded in _NON_ARTICLE_NUMBER_WORDS
            ):
                break
            # Uma letra maiúscula isolada é comumente uma variável de
            # fórmula (``A A``), não um falso início de palavra.
            if (
                len(current.text) == 1
                and current.text.isupper()
                and current.text != "A"
            ) or (
                len(following.text) == 1
                and following.text.isupper()
                and following.text != "A"
            ):
                break
            separator = line[words[run_end - 1].end : following.start]
            if not _repeat_separator(separator):
                break
            if _in_ranges(following.start, following.end, protected):
                break
            if _looks_like_math(line, current.start, following.end):
                break
            run_end += 1
        if run_end > index + 1:
            first = words[index]
            last = words[run_end - 1]
            if not _in_ranges(first.start, first.end, protected):
                deletions.append(
                    (first.end, last.end, line[first.end : last.end], "repetition")
                )
                for repeated in words[index + 1 : run_end]:
                    log.repetitions.append(repeated.text)
            index = run_end
            continue
        index += 1
    return _apply_deletions(line, deletions)


def _remove_phrase_repetitions_from_line(
    line: str, log: _RemovalLog
) -> str:
    """Remove uma pequena sequência repetida, sem tocar em fórmulas."""

    words = _lexical_words(line)
    if len(words) < 4:
        return line
    protected = _protected_ranges(line)
    deletions: list[tuple[int, int, str, str]] = []
    occupied: list[tuple[int, int]] = []
    max_length = min(6, len(words) // 2)

    for length in range(2, max_length + 1):
        index = 0
        while index + 2 * length <= len(words):
            first = words[index : index + length]
            second = words[index + length : index + 2 * length]
            matches = all(
                left.folded == right.folded for left, right in zip(first, second)
            )
            if not matches:
                index += 1
                continue
            if any(_in_ranges(word.start, word.end, protected) for word in first + second):
                index += 1
                continue
            if any(word.folded in _NON_ARTICLE_NUMBER_WORDS for word in first + second):
                index += 1
                continue
            if any(
                len(word.text) == 1
                and word.text.isupper()
                and word.text != "A"
                for word in first + second
            ):
                index += 1
                continue
            if all(len(word.text) == 1 for word in first + second):
                index += 1
                continue
            if _looks_like_math(line, first[0].start, second[-1].end):
                index += 1
                continue
            separator = line[first[-1].end : second[0].start]
            if not _repeat_separator(separator):
                index += 1
                continue
            # Uma frase composta apenas de palavras funcionais pode ser
            # gramatical; pelo menos um termo com conteúdo torna a repetição
            # repetição obviamente acidental para esta etapa.
            if all(word.folded in _REPETITION_FUNCTION_WORDS for word in first):
                index += 1
                continue
            # A primeira ocorrência completa da frase permanece; somente
            # a segunda (e o separador trivial) é removida.
            start = first[-1].end
            end = second[-1].end
            if any(start < right and end > left for left, right in occupied):
                index += 1
                continue
            deletions.append((start, end, line[start:end], "repetition"))
            occupied.append((start, end))
            for repeated in second:
                log.repetitions.append(repeated.text)
            index += 2 * length
    return _apply_deletions(line, deletions)


def _remove_repetitions_from_line(
    line: str, config: FilterConfig, log: _RemovalLog
) -> str:
    if not config.remove_repetitions:
        return line
    line = _remove_single_repetitions_from_line(line, log)
    return _remove_phrase_repetitions_from_line(line, log)


def _normalize_line_spacing(line: str) -> str:
    line = line.replace("\u00a0", " ").replace("\u200b", "")
    line = _HORIZONTAL_SPACE_RE.sub(" ", line)
    line = line.strip()

    # Ajustes conservativeis de pontuação.  O ponto entre dígitos não é
    # alterado, para não transformar uma transcrição numérica em decimal.
    # Linhas que parecem fórmulas mantêm até a pontuação original.
    math_like = _looks_like_math(line, 0, len(line)) if line else False
    if not math_like:
        line = re.sub(r" +([,;:!?%\)\]\}])", r"\1", line)
        line = re.sub(r"([,;:])(?=[^\s\)\]\}])", r"\1 ", line)
        line = re.sub(r"([\(\[\{]) +", r"\1", line)
        line = re.sub(r" +([\)\]\}])", r"\1", line)
        line = re.sub(r"(?<!\d) +\.(?!\d)", ".", line)

    # Delimitadores órfãos podem sobrar quando um filler era o único
    # elemento entre duas vírgulas.  Não removemos ?, ! ou . para preservar
    # perguntas e a pontuação original.
    line = re.sub(r"^[\s,;:]+", "", line)
    line = re.sub(r"[\s,;:]+$", "", line)
    return line.strip()


def _is_silence_only_line(line: str, config: FilterConfig) -> bool:
    if not config.remove_silence or not config.silence_tokens:
        return False
    return bool(_silence_spans(line.strip(), config.silence_tokens))


def _is_orphan_punctuation(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and all(character in ".,;:!?–—…" for character in stripped)


def _transform(
    value: str | None, config: FilterConfig
) -> FilterResult:
    original = _coerce_text(value)
    log = _RemovalLog(fillers=[], repetitions=[], silence=[])
    if not original:
        return FilterResult(original_text=original, filtered_text="")

    normalized_newlines = original.replace("\r\n", "\n").replace("\r", "\n")
    output_lines: list[str] = []
    for raw_line in normalized_newlines.split("\n"):
        silence_only = _is_silence_only_line(raw_line, config)
        filler_count_before = len(log.fillers)
        silence_count_before = len(log.silence)
        line = _remove_silence_from_line(raw_line, config, log)
        line = _remove_fillers_from_line(line, config, log)
        line = _remove_repetitions_from_line(line, config, log)
        if config.normalize_whitespace:
            line = _normalize_line_spacing(line)
        else:
            line = line.strip()
        if silence_only and not line:
            continue
        if (
            len(log.fillers) > filler_count_before
            or len(log.silence) > silence_count_before
        ) and _is_orphan_punctuation(line):
            line = ""
        if not line and (
            silence_only
            or len(log.fillers) > filler_count_before
            or len(log.silence) > silence_count_before
        ):
            continue
        output_lines.append(line)

    filtered = "\n".join(output_lines)
    if config.normalize_whitespace:
        filtered = re.sub(r"\n{3,}", "\n\n", filtered).strip()
    else:
        filtered = filtered.strip()
    if not filtered:
        return FilterResult(
            original_text=original,
            filtered_text="",
            removed_fillers=tuple(log.fillers),
            removed_repetitions=tuple(log.repetitions),
            removed_silence_tokens=tuple(log.silence),
        )
    return FilterResult(
        original_text=original,
        filtered_text=filtered,
        removed_fillers=tuple(log.fillers),
        removed_repetitions=tuple(log.repetitions),
        removed_silence_tokens=tuple(log.silence),
    )


class TranscriptFilter:
    """Filtro reutilizável para uma transcrição de aula.

    A classe não mantém estado entre chamadas.  Isso torna o resultado
    determinístico e permite usar a mesma instância em testes,CLI ou
    workers.  ``filter`` é a forma simples; ``process`` expõe metadados.
    """

    def __init__(self, config: FilterConfig | None = None) -> None:
        self.config = config or FilterConfig()

    def process(
        self, text: str | None, config: FilterConfig | None = None
    ) -> FilterResult:
        """Filtra ``text`` e retorna texto original, final e remoções."""

        return _transform(text, config or self.config)

    def filter(self, text: str | None, config: FilterConfig | None = None) -> str:
        """Filtra ``text`` e retorna somente a transcrição limpa."""

        return self.process(text, config).filtered_text

    def clean(self, text: str | None, config: FilterConfig | None = None) -> str:
        """Alias semântico de :meth:`filter`."""

        return self.filter(text, config)

    def filter_transcript(
        self, text: str | None, config: FilterConfig | None = None
    ) -> str:
        """Alias explícito de :meth:`filter` para integrações."""

        return self.filter(text, config)

    def filter_result(
        self, text: str | None, config: FilterConfig | None = None
    ) -> FilterResult:
        """Alias explícito de :meth:`process`."""

        return self.process(text, config)

    def __call__(self, text: str | None, config: FilterConfig | None = None) -> str:
        return self.filter(text, config)


def filter_transcript_result(
    text: str | None, config: FilterConfig | None = None
) -> FilterResult:
    """API simples para quem precisa dos metadados de uma filtragem."""

    return _transform(text, config or FilterConfig())


def filter_transcript(text: str | None, config: FilterConfig | None = None) -> str:
    """Limpa uma transcrição usando apenas a biblioteca padrão.

    Entradas vazias (``\"\"`` ou ``None``) retornam ``\"\"``.  Nenhuma regra
    tenta decidir se uma frase é relevante para a disciplina; a função apenas
    remove ruído lexicalmente seguro.
    """

    return filter_transcript_result(text, config).filtered_text


def clean_transcript(text: str | None, config: FilterConfig | None = None) -> str:
    """Alias legível de :func:`filter_transcript`."""

    return filter_transcript(text, config)


def filter_text(text: str | None, config: FilterConfig | None = None) -> str:
    """Alias curto de :func:`filter_transcript` para integrações simples."""

    return filter_transcript(text, config)


def _config_with(config: FilterConfig | None, **changes: object) -> FilterConfig:
    base = config or FilterConfig()
    values = {
        "filler_words": base.filler_words,
        "filler_phrases": base.filler_phrases,
        "silence_tokens": base.silence_tokens,
        "remove_fillers": base.remove_fillers,
        "remove_repetitions": base.remove_repetitions,
        "remove_silence": base.remove_silence,
        "normalize_whitespace": base.normalize_whitespace,
    }
    values.update(changes)
    return FilterConfig(**values)  # type: ignore[arg-type]


def remove_fillers(text: str | None, config: FilterConfig | None = None) -> str:
    """Remove fillers e normaliza espaços, sem repetir outras etapas."""

    return filter_transcript(
        text,
        _config_with(
            config,
            remove_fillers=True,
            remove_repetitions=False,
            remove_silence=False,
        ),
    )


def remove_consecutive_repetitions(
    text: str | None, config: FilterConfig | None = None
) -> str:
    """Remove repetições lexicais consecutivas, preservando números e fórmulas."""

    return filter_transcript(
        text,
        _config_with(
            config,
            remove_fillers=False,
            remove_repetitions=True,
            remove_silence=False,
        ),
    )


def remove_repetitions(
    text: str | None, config: FilterConfig | None = None
) -> str:
    """Alias de :func:`remove_consecutive_repetitions`."""

    return remove_consecutive_repetitions(text, config)


def remove_silence_tokens(
    text: str | None, config: FilterConfig | None = None
) -> str:
    """Remove marcadores explícitos de silêncio e normaliza espaços."""

    return filter_transcript(
        text,
        _config_with(
            config,
            remove_fillers=False,
            remove_repetitions=False,
            remove_silence=True,
        ),
    )


def normalize_spaces(text: str | None) -> str:
    """Normaliza apenas espaços horizontais, sem remover conteúdo."""

    original = _coerce_text(text)
    if not original:
        return ""
    lines = original.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    normalized = "\n".join(_normalize_line_spacing(line) for line in lines)
    return re.sub(r"\n{3,}", "\n\n", normalized).strip()


# Nomes mantidos como aliases para tornar a API fácil de descobrir em código
# existente sem exigir um pipeline ou uma camada de integração adicional.
FilteringResult = FilterResult
FilteringConfig = FilterConfig
FilterOptions = FilterConfig
TranscriptFilterConfig = FilterConfig
DEFAULT_FILLERS = DEFAULT_FILLER_WORDS
SILENCE_TOKENS = DEFAULT_SILENCE_TOKENS
normalize_whitespace = normalize_spaces
clean_transcription = filter_transcript
filter_transcription = filter_transcript
clean_text = filter_transcript

__all__ = [
    "DEFAULT_FILLER_PHRASES",
    "DEFAULT_FILLER_WORDS",
    "DEFAULT_FILLERS",
    "DEFAULT_SILENCE_TOKENS",
    "SILENCE_TOKENS",
    "FilterConfig",
    "FilterOptions",
    "FilterResult",
    "FilteringConfig",
    "FilteringResult",
    "TranscriptFilter",
    "TranscriptFilterConfig",
    "clean_text",
    "clean_transcript",
    "clean_transcription",
    "filter_text",
    "filter_transcript",
    "filter_transcript_result",
    "filter_transcription",
    "normalize_spaces",
    "normalize_whitespace",
    "remove_consecutive_repetitions",
    "remove_fillers",
    "remove_repetitions",
    "remove_silence_tokens",
]
