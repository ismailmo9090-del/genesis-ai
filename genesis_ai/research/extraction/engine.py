"""Information extraction engine using simple NLP patterns."""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Fact:
    claim: str
    confidence: float = 0.5
    evidence: str = ""


@dataclass
class CodeSnippet:
    language: str
    code: str
    description: str = ""


SENTENCE_END = re.compile(r'(?<=[.!?])\s+(?=[A-Z"\'(\[])')
DEFINITION_PATTERN = re.compile(
    r'(?P<term>[A-Z][a-zA-Z\s]{1,40})\s+(?:is|are|refers to|means|denotes|is defined as)\s+(?P<def>[^.!?\n]{10,200})',
    re.IGNORECASE,
)
CODE_BLOCK = re.compile(r'```(\w*)\n(.*?)```', re.DOTALL)
INLINE_CODE = re.compile(r'`([^`\n]{5,500})`')
HEADING_PATTERN = re.compile(r'^#{1,6}\s+(.+)', re.MULTILINE)
KEYWORD_PATTERNS = {
    "definition": re.compile(r'\b(is defined as|means|refers to|is a type of)\b', re.IGNORECASE),
    "causal": re.compile(r'\b(because|due to|causes|results in|leads to|as a result)\b', re.IGNORECASE),
    "comparison": re.compile(r'\b(compared to|versus|is better than|is worse than|differ|similar)\b', re.IGNORECASE),
    "temporal": re.compile(r'\b(before|after|during|since|until|first|then|finally)\b', re.IGNORECASE),
    "conditional": re.compile(r'\b(if|unless|provided that|assuming|when)\b', re.IGNORECASE),
    "quantitative": re.compile(r'\b\d+(\.\d+)?\s*(%|percent|times|fold|million|billion|thousand)\b', re.IGNORECASE),
}

STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "out", "off", "over",
    "under", "again", "further", "then", "once", "here", "there", "when",
    "where", "why", "how", "all", "each", "every", "both", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "just", "that", "this", "these",
    "those", "and", "but", "or", "if", "it", "its", "he", "she", "they",
    "we", "you", "me", "him", "her", "us", "them", "my", "your", "his",
    "our", "their", "what", "which", "who", "whom",
})


class InformationExtraction:
    """Extract facts, concepts, code, and definitions from text using pattern matching."""

    def extract_facts(self, text: str) -> list[Fact]:
        if not text or not text.strip():
            return []
        sentences = self._split_sentences(text)
        facts: list[Fact] = []
        for sentence in sentences:
            cleaned = sentence.strip()
            if len(cleaned) < 15:
                continue
            confidence = self._estimate_fact_confidence(cleaned)
            if confidence < 0.2:
                continue
            evidence = self._find_supporting_evidence(cleaned, text)
            facts.append(Fact(
                claim=cleaned,
                confidence=confidence,
                evidence=evidence,
            ))
        return self._deduplicate_facts(facts)

    def extract_concepts(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []
        headings = self._extract_headings(text)
        noun_phrases = self._extract_noun_phrases(text)
        capitalized = self._extract_capitalized_terms(text)
        all_candidates = headings + noun_phrases + capitalized
        freq: dict[str, int] = {}
        for term in all_candidates:
            key = term.lower().strip()
            if key in STOP_WORDS or len(key) < 3:
                continue
            freq[key] = freq.get(key, 0) + 1
        sorted_terms = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        seen: set[str] = set()
        concepts: list[str] = []
        for term, count in sorted_terms:
            normalized = term.lower()
            if normalized not in seen and count >= 1:
                seen.add(normalized)
                concepts.append(term)
        return concepts[:30]

    def extract_code(self, text: str) -> list[CodeSnippet]:
        if not text:
            return []
        snippets: list[CodeSnippet] = []
        for match in CODE_BLOCK.finditer(text):
            lang = match.group(1) or "unknown"
            code = match.group(2).strip()
            if code:
                description = self._describe_code_block(code, lang)
                snippets.append(CodeSnippet(language=lang, code=code, description=description))
        for match in INLINE_CODE.finditer(text):
            code = match.group(1).strip()
            if self._looks_like_code(code):
                lang = self._guess_language(code)
                snippets.append(CodeSnippet(language=lang, code=code, description="Inline code"))
        return snippets

    def extract_definitions(self, text: str) -> list[tuple[str, str]]:
        if not text or not text.strip():
            return []
        definitions: list[tuple[str, str]] = []
        seen: set[str] = set()
        for match in DEFINITION_PATTERN.finditer(text):
            term = match.group("term").strip()
            definition = match.group("def").strip()
            key = term.lower()
            if key in seen or len(term) < 2:
                continue
            seen.add(key)
            definitions.append((term, definition))
        sentence_defs = self._extract_sentence_definitions(text)
        for term, definition in sentence_defs:
            key = term.lower()
            if key not in seen:
                seen.add(key)
                definitions.append((term, definition))
        return definitions

    def _split_sentences(self, text: str) -> list[str]:
        parts = SENTENCE_END.split(text)
        return [p.strip() for p in parts if p.strip()]

    def _estimate_fact_confidence(self, sentence: str) -> float:
        score = 0.3
        if re.match(r'^[A-Z]', sentence):
            score += 0.1
        if sentence.endswith(('.', '!', '?')):
            score += 0.05
        for pattern in KEYWORD_PATTERNS.values():
            if pattern.search(sentence):
                score += 0.1
                break
        has_number = bool(re.search(r'\d+', sentence))
        if has_number:
            score += 0.1
        has_qualifier = bool(re.search(
            r'\b(maybe|perhaps|possibly|might|could|some|many|often|usually|generally)\b',
            sentence, re.IGNORECASE,
        ))
        if has_qualifier:
            score -= 0.15
        has_hedge = bool(re.search(
            r'\b(believe|think|opinion|feel|seem|appear)\b',
            sentence, re.IGNORECASE,
        ))
        if has_hedge:
            score -= 0.1
        negation = bool(re.search(r"\b(not|never|no|neither|nor|don't|doesn't|isn't)\b", sentence, re.IGNORECASE))
        if negation:
            score += 0.05
        return max(0.0, min(1.0, score))

    def _find_supporting_evidence(self, sentence: str, full_text: str) -> str:
        keywords = [
            w.lower() for w in sentence.split()
            if w.lower() not in STOP_WORDS and len(w) > 3
        ][:5]
        if not keywords:
            return ""
        sentences = self._split_sentences(full_text)
        for candidate in sentences:
            candidate_lower = candidate.lower()
            if candidate.strip() == sentence.strip():
                continue
            matches = sum(1 for kw in keywords if kw in candidate_lower)
            if matches >= 2:
                return candidate.strip()
        return ""

    def _deduplicate_facts(self, facts: list[Fact]) -> list[Fact]:
        seen: set[str] = set()
        unique: list[Fact] = []
        for fact in facts:
            key = fact.claim.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(fact)
        return unique

    def _extract_headings(self, text: str) -> list[str]:
        return [m.strip() for m in HEADING_PATTERN.findall(text)]

    def _extract_noun_phrases(self, text: str) -> list[str]:
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
        bigrams: list[str] = []
        for i in range(len(words) - 1):
            w1 = words[i].lower()
            w2 = words[i + 1].lower()
            if w1 not in STOP_WORDS or w2 not in STOP_WORDS:
                if w1 not in STOP_WORDS and w2 not in STOP_WORDS:
                    bigrams.append(f"{words[i]} {words[i + 1]}")
        return bigrams

    def _extract_capitalized_terms(self, text: str) -> list[str]:
        pattern = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b')
        return pattern.findall(text)

    def _extract_sentence_definitions(self, text: str) -> list[tuple[str, str]]:
        definitions: list[tuple[str, str]] = []
        patterns = [
            re.compile(r'(.{2,40})\s+is\s+(?:a|an|the)\s+(.{10,200})', re.IGNORECASE),
            re.compile(r'(.{2,40})\s+are\s+(?:a|an|the)\s+(.{10,200})', re.IGNORECASE),
            re.compile(r'(?:the|a|an)\s+(.{2,40})\s+(?:is|are)\s+(?:a|an)\s+(.{10,200})', re.IGNORECASE),
        ]
        for pattern in patterns:
            for match in pattern.finditer(text):
                term = match.group(1).strip()
                definition = match.group(2).strip()
                if len(term) >= 3 and len(definition) >= 10:
                    definitions.append((term, definition))
        return definitions

    def _describe_code_block(self, code: str, lang: str) -> str:
        lines = code.strip().split('\n')
        first_line = lines[0].strip() if lines else ""
        if lang in ("python", "py"):
            if "def " in first_line:
                func_name = re.search(r'def\s+(\w+)', first_line)
                return f"Python function: {func_name.group(1)}" if func_name else "Python function"
            if "class " in first_line:
                class_name = re.search(r'class\s+(\w+)', first_line)
                return f"Python class: {class_name.group(1)}" if class_name else "Python class"
            if "import " in first_line or "from " in first_line:
                return "Python imports"
        elif lang in ("javascript", "js"):
            if "function " in first_line or "=>" in first_line:
                return "JavaScript function"
            if "const " in first_line or "let " in first_line or "var " in first_line:
                return "JavaScript declaration"
        elif lang in ("bash", "sh", "shell"):
            return "Shell command"
        elif lang == "sql":
            return "SQL query"
        elif lang in ("json",):
            return "JSON data"
        return f"{lang} code snippet" if lang and lang != "unknown" else "Code snippet"

    def _looks_like_code(self, text: str) -> bool:
        code_indicators = [
            r'\w+\s*\(', r'\w+\.\w+\(', r'=\s*\w+', r'->',
            r'::', r'\w+\[', r'\{.*\}', r'\(.*\)',
            r'import\s', r'from\s+\w+\s+import', r'def\s+\w+',
            r'function\s+\w+', r'const\s+\w+', r'var\s+\w+',
        ]
        matches = sum(1 for p in code_indicators if re.search(p, text))
        return matches >= 2

    def _guess_language(self, code: str) -> str:
        if re.search(r'\bdef\s+\w+\s*\(', code):
            return "python"
        if re.search(r'\bfunction\s+\w+\s*\(', code):
            return "javascript"
        if re.search(r'\bSELECT\b.*\bFROM\b', code, re.IGNORECASE):
            return "sql"
        if re.search(r'\bif\s*\(', code) and re.search(r'\{', code):
            return "javascript"
        if re.search(r'\bprint\s*\(', code):
            return "python"
        if re.search(r'\becho\b', code):
            return "bash"
        return "unknown"
