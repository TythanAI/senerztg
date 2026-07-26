"""Text Toolkit — slugs, transliteration, readability, keywords, summaries.

The transliteration table covers Cyrillic and common European diacritics,
which is exactly the case that breaks naive `unicodedata` slugifiers.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from saascore.app import ServiceSpec

CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e",
    "ю": "yu", "я": "ya",
    # Ukrainian / Belarusian extras
    "і": "i", "ї": "yi", "є": "ye", "ґ": "g", "ў": "u",
}

EXTRA = {
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "å": "aa", "æ": "ae", "ø": "oe",
    "ñ": "n", "ç": "c", "ł": "l", "đ": "d", "þ": "th", "ð": "d",
}

STOPWORDS = {
    "en": {
        "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at", "for",
        "with", "is", "are", "was", "were", "be", "been", "it", "its", "this",
        "that", "these", "those", "as", "by", "from", "has", "have", "had", "you",
        "your", "we", "our", "they", "their", "he", "she", "his", "her", "not",
        "can", "will", "would", "there", "which", "when", "what", "how", "all",
    },
    "ru": {
        "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то",
        "все", "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за",
        "бы", "по", "только", "ее", "мне", "было", "вот", "от", "меня", "еще",
        "нет", "о", "из", "ему", "теперь", "когда", "даже", "ну", "вдруг", "ли",
        "если", "уже", "или", "быть", "был", "него", "до", "вас", "их", "для",
    },
}


class SlugRequest(BaseModel):
    text: str = Field(..., max_length=2000)
    separator: str = Field("-", max_length=1)
    lowercase: bool = True
    max_length: int = Field(80, ge=1, le=500)


class AnalyzeRequest(BaseModel):
    text: str = Field(..., max_length=100_000)
    language: str = Field("en", description="'en' or 'ru' — picks the stopword list")
    keywords: int = Field(10, ge=1, le=50)


class SummarizeRequest(BaseModel):
    text: str = Field(..., max_length=100_000)
    sentences: int = Field(3, ge=1, le=20)
    language: str = Field("en")


def transliterate(text: str) -> str:
    out = []
    for char in text:
        lower = char.lower()
        replacement = CYRILLIC.get(lower) or EXTRA.get(lower)
        if replacement is not None:
            out.append(replacement.upper() if char.isupper() and replacement else replacement)
        else:
            out.append(char)
    decomposed = unicodedata.normalize("NFKD", "".join(out))
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def slugify(text: str, separator: str = "-", lowercase: bool = True, limit: int = 80) -> str:
    slug = transliterate(text)
    if lowercase:
        slug = slug.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", separator or "-", slug).strip(separator or "-")
    if len(slug) > limit:
        # Cut on a separator so the slug never ends mid-word.
        slug = slug[:limit].rsplit(separator or "-", 1)[0] or slug[:limit]
    return slug


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+(?=[A-ZА-ЯЁ0-9])", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _words(text: str) -> list[str]:
    return re.findall(r"\b[\w'-]+\b", text.lower())


def _syllables(word: str) -> int:
    vowels = "aeiouyаеёиоуыэюя"
    count, previous_vowel = 0, False
    for char in word.lower():
        is_vowel = char in vowels
        if is_vowel and not previous_vowel:
            count += 1
        previous_vowel = is_vowel
    return max(1, count)


def build_router() -> APIRouter:
    router = APIRouter()

    @router.post("/text/slug")
    async def slug(request: Request, body: SlugRequest) -> dict:
        """URL-safe slug with Cyrillic and diacritic transliteration."""
        await request.app.state.require_key(request)
        result = slugify(body.text, body.separator, body.lowercase, body.max_length)
        return {
            "slug": result,
            "transliterated": transliterate(body.text),
            "length": len(result),
        }

    @router.post("/text/analyze")
    async def analyze(request: Request, body: AnalyzeRequest) -> dict:
        """Counts, readability and the keywords that carry the text."""
        await request.app.state.require_key(request)
        text = body.text.strip()
        if not text:
            raise HTTPException(400, "text must not be empty")

        words = _words(text)
        sentences = _sentences(text)
        stop = STOPWORDS.get(body.language, STOPWORDS["en"])

        meaningful = [w for w in words if w not in stop and len(w) > 2]
        frequencies = Counter(meaningful)

        syllables = sum(_syllables(w) for w in words) if words else 0
        words_per_sentence = len(words) / len(sentences) if sentences else 0
        syllables_per_word = syllables / len(words) if words else 0

        # Flesch reading ease — the standard readability yardstick.
        flesch = 206.835 - 1.015 * words_per_sentence - 84.6 * syllables_per_word
        flesch = round(max(0.0, min(100.0, flesch)), 1)

        if flesch >= 80:
            grade = "very easy"
        elif flesch >= 60:
            grade = "plain English"
        elif flesch >= 40:
            grade = "fairly difficult"
        else:
            grade = "difficult"

        return {
            "characters": len(text),
            "characters_no_spaces": len(re.sub(r"\s", "", text)),
            "words": len(words),
            "unique_words": len(set(words)),
            "sentences": len(sentences),
            "paragraphs": len([p for p in text.split("\n\n") if p.strip()]),
            "avg_words_per_sentence": round(words_per_sentence, 1),
            "reading_time_minutes": round(len(words) / 200, 1),
            "speaking_time_minutes": round(len(words) / 130, 1),
            "flesch_reading_ease": flesch,
            "readability": grade,
            "keywords": [
                {"word": word, "count": count, "density": round(count / max(1, len(words)) * 100, 2)}
                for word, count in frequencies.most_common(body.keywords)
            ],
        }

    @router.post("/text/summarize")
    async def summarize(request: Request, body: SummarizeRequest) -> dict:
        """Extractive summary: keeps the highest-scoring original sentences."""
        await request.app.state.require_key(request)
        sentences = _sentences(body.text)
        if not sentences:
            raise HTTPException(400, "Could not find any sentences in the text")
        if len(sentences) <= body.sentences:
            return {"summary": body.text.strip(), "sentences": len(sentences), "compression": 1.0}

        stop = STOPWORDS.get(body.language, STOPWORDS["en"])
        words = [w for w in _words(body.text) if w not in stop and len(w) > 2]
        frequencies = Counter(words)
        if not frequencies:
            raise HTTPException(400, "Text has no scoreable content")
        peak = max(frequencies.values())

        scored = []
        for position, sentence in enumerate(sentences):
            terms = [w for w in _words(sentence) if w in frequencies]
            if not terms:
                score = 0.0
            else:
                score = sum(frequencies[w] / peak for w in terms) / math.sqrt(len(terms))
            # A gentle lead bias: openings carry the thesis more often than not.
            score *= 1.0 + max(0.0, (len(sentences) - position) / (len(sentences) * 8))
            scored.append((score, position, sentence))

        best = sorted(scored, reverse=True)[: body.sentences]
        ordered = [sentence for _, _, sentence in sorted(best, key=lambda item: item[1])]
        summary = " ".join(ordered)

        return {
            "summary": summary,
            "sentences": len(ordered),
            "original_sentences": len(sentences),
            "compression": round(len(summary) / max(1, len(body.text)), 3),
        }

    @router.post("/text/case")
    async def case(request: Request, text: str, style: str = "snake") -> dict:
        """Convert an identifier between snake, camel, pascal, kebab and title case."""
        await request.app.state.require_key(request)
        parts = [p for p in re.split(r"[\s_-]+|(?<=[a-z])(?=[A-Z])", text) if p]
        if not parts:
            raise HTTPException(400, "text must contain at least one word")

        styles = {
            "snake": "_".join(p.lower() for p in parts),
            "kebab": "-".join(p.lower() for p in parts),
            "camel": parts[0].lower() + "".join(p.capitalize() for p in parts[1:]),
            "pascal": "".join(p.capitalize() for p in parts),
            "constant": "_".join(p.upper() for p in parts),
            "title": " ".join(p.capitalize() for p in parts),
        }
        if style not in styles:
            raise HTTPException(400, f"style must be one of: {', '.join(styles)}")
        return {"result": styles[style], "all_styles": styles}

    return router


def spec() -> ServiceSpec:
    return ServiceSpec(
        name="textkit",
        title="Text Toolkit API",
        tagline="Slugs that survive Cyrillic, plus readability, keywords and summaries.",
        summary="Transliterate and slugify, analyse readability and keyword density, produce extractive summaries.",
        router=build_router(),
        endpoints=[
            ("POST /v1/text/slug", "URL-safe slug with transliteration"),
            ("POST /v1/text/analyze", "Counts, readability, keyword density"),
            ("POST /v1/text/summarize", "Extractive summary"),
            ("POST /v1/text/case", "snake / camel / pascal / kebab conversion"),
        ],
        example=(
            'curl -X POST https://api.example.com/v1/text/slug \\\n'
            '  -H "Authorization: Bearer sk_live_..." \\\n'
            '  -d \'{"text":"Привет, мир! Как дела?"}\'   # → privet-mir-kak-dela'
        ),
    )
