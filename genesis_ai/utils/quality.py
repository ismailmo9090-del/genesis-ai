"""Generic quality scoring for text snippets.

Replaces hardcoded domain-specific pattern lists with a universal
quality scorer that works for any domain, any language (English, Hindi, Hinglish).
"""

import re

# Hindi/Hinglish verb markers (generic language features)
_HINDI_VERBS = (
    'है', 'हैं', 'था', 'थे', 'थी', 'होगा', 'होगी', 'कर', 'करता', 'करती',
    'जा', 'आ', 'दे', 'ले', 'बोल', 'लिख', 'पढ़', 'बना', 'चल', 'रख',
    'देख', 'सुन', 'मिल', 'पा', 'रह', 'सक', 'करे', 'करें', 'हो', 'हों',
)
_HINGLISH_VERBS = (
    'hai', 'tha', 'the', 'thi', 'hoga', 'hogi', 'karta', 'karti', 'kare',
    'ja', 'aa', 'de', 'le', 'bol', 'likh', 'padh', 'bana', 'chal', 'rakh',
    'dekh', 'sun', 'mil', 'pa', 'raha', 'rahi', 'sak', 'ho', 'hain',
)
# Hindi danda (purna viram)
_DANDA = '\u0964'
_DEVANAGARI_RANGE = re.compile(r'[\u0900-\u097F]')

# ── Navigation/Chrome Detection ──────────────────────────────────────────────

# Universal UI/chrome vocabulary — appears on almost ALL websites regardless
# of subject matter. These are structural elements of web pages, not content.
_NAV_CHROME_PHRASES = [
    # Navigation actions
    r'\b(skip to content|skip to main|skip navigation|jump to content)\b',
    r'\b(main menu|site navigation|toggle navigation|open menu|close menu)\b',
    r'\b(move to sidebar|back to top|breadcrumb|breadcrumbs)\b',
    # Legal/policy
    r'\b(cookie|accept cookies|privacy policy|terms of service|terms and conditions)\b',
    # Engagement prompts
    r'\b(subscribe|newsletter|sign up|log in|sign in|register)\b',
    r'\b(follow us|share this|related articles|you might also like)\b',
    # Advertising
    r'\b(advertisement|sponsored|ads by|ad by)\b',
    # Reading meta
    r'\b(read more|last updated|min read|comments|leave a reply)\b',
    # Structure
    r'\b(table of contents|search search|footer|all rights reserved)\b',
    r'\b(home|about|contact|services|products|features|pricing|faq)\b',
    # Common chrome fragments (pipe-separated or space-separated menus)
    r'\b(view all|learn more|click here|show more|load more|see all)\b',
    # Category/breadcrumb navigation (e.g. "Categories > Physics > Magnetism")
    r'\b(categories?|tags?|topics?)\s*[:/|>]\s*\w+\s*[:/|>]',
    r'\w+\s*[:/|]\s*\w+\s*[:/|]\s*\w+\s*[:/|]',  # 3+ levels of navigation
    r'\bPE\s+Categories\b',
    r'\bPhysics Explained\b',
]


def _is_nav_chrome(text: str) -> bool:
    """Detect navigation/chrome text using universal structural properties.

    Two signals:
    1. Phrase matching: broad UI vocabulary (works for any website)
    2. Structural signal: menu density — many short fragments, few real sentences
    3. Slash/pipe navigation: breadcrumb-style paths like "Home > Physics > Magnetism"
    """
    text_lower = text.lower().strip()

    # Signal 1: Phrase list matches
    phrase_hits = 0
    for pat in _NAV_CHROME_PHRASES:
        if re.search(pat, text_lower):
            phrase_hits += 1

    # Signal 1b: Slash/pipe navigation detection (e.g. "Home / Physics / Magnetism")
    # Count slash-separated segments where segments are short (< 5 words)
    slash_segments = re.split(r'\s*[/|]\s*', text.strip())
    if len(slash_segments) >= 3:
        short_segs = sum(1 for s in slash_segments if len(s.split()) <= 4)
        if short_segs >= len(slash_segments) * 0.7:
            phrase_hits += 2  # Strong signal

    # Signal 2: Structural — menu density
    fragments = re.split(r'\s*[|\n]\s*|\s{2,}', text.strip())
    short_fragments = 0
    for frag in fragments:
        frag = frag.strip()
        if not frag:
            continue
        word_count = len(frag.split())
        has_terminal_punct = bool(re.search(r'[.!?]$', frag))
        has_internal_punct = bool(re.search(r'[,;:]', frag))
        if word_count <= 3 and not has_terminal_punct and not has_internal_punct:
            short_fragments += 1

    first_150 = text[:150]
    sentence_count = len(re.findall(
        r'[A-Z\u0900-\u097F].*\b(is|are|was|were|has|have|can|will|do|does|'
        r'make|cook|write|create|learn|use|provide|go|come|run|take|see|know)\b.*[.!?]',
        first_150,
    ))

    total_fragments = max(len([f for f in fragments if f.strip()]), 1)
    menu_density = short_fragments / total_fragments

    structural_signal = (menu_density > 0.5 and sentence_count < 2 and short_fragments >= 3)

    return phrase_hits >= 2 or structural_signal


def _is_devanagari(ch: str) -> bool:
    return bool(_DEVANAGARI_RANGE.match(ch))


def _has_devanagari(text: str) -> bool:
    return bool(_DEVANAGARI_RANGE.search(text))


def _has_encoding_failure(text: str) -> bool:
    """Detect Unicode decode failure artifacts (3+ consecutive ? marks)."""
    return bool(re.search(r'\?{3,}', text))


def _has_hashtag_spam(text: str) -> bool:
    """Detect excessive hashtag usage (3+ hashtags = likely spam/social media)."""
    hashtags = re.findall(r'#\w+', text)
    return len(hashtags) >= 3


def _has_self_promotion(text: str) -> bool:
    """Detect self-promotional / engagement-bait text."""
    promo_patterns = [
        r'\b(subscribe\s+(to\s+)?(my|our|the)\s+channel)\b',
        r'\b(don\'?t\s+miss)\b',
        r'\b(like\s+and\s+share)\b',
        r'\b(follow\s+me)\b',
        r'\b(check\s+out\s+my)\b',
        r'\b(my\s+channel)\b',
        r'\b(please\s+subscribe)\b',
        r'\b(like\s+share\s+subscribe)\b',
    ]
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in promo_patterns)


def quality_score(text: str, query: str = "") -> float:
    """Score a text snippet for quality and relevance. Returns 0.0 to 1.0.

    Works for English, Hindi, and Hinglish text.
    """
    if not text or not text.strip():
        return 0.0

    text = text.strip()
    score = 0.5  # baseline

    # 1. LENGTH check
    if len(text) < 20:
        return 0.1
    if len(text) > 500:
        score -= 0.2

    # 2. ENCODING check — reject HTML/JSON/CSS
    if '<' in text[:50] or '{' in text[:50]:
        return 0.0
    if re.search(r'<[^>]+>', text[:100]):
        return 0.0

    # 2b. ENCODING FAILURE — reject text with Unicode decode artifacts
    if _has_encoding_failure(text):
        return 0.0

    # 2c. HASHTAG SPAM — reject social media spam
    if _has_hashtag_spam(text):
        return 0.05

    # 2d. SELF-PROMOTION — reject engagement bait
    if _has_self_promotion(text):
        return 0.05

    # 3. ALPHA RATIO — reject mostly numbers/symbols
    # Count Devanagari characters as alpha
    alpha_count = sum(
        1 for c in text
        if c.isalpha() or c.isspace() or _is_devanagari(c)
    )
    alpha_ratio = alpha_count / max(len(text), 1)
    if alpha_ratio < 0.6:
        return 0.1

    # 4. NAVIGATION/CHROME detection (generic, structural)
    if _is_nav_chrome(text):
        return 0.1  # reject navigation text

    # 4b. INFOBOX/DATA-JUNK detection — reject structured data that isn't prose
    # Hex color codes (e.g. "#87CEEB", "#FFF")
    if re.search(r'#[0-9A-Fa-f]{3,8}\b', text):
        return 0.05
    # Pipe-delimited key-value pairs (infobox tables)
    if text.count('|') >= 3:
        return 0.05
    # Coordinate/color data patterns
    if re.search(r'\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)', text):
        return 0.05
    # Wikipedia "redirects here" / "For other uses" artifacts
    if re.search(r'redirects?\s+here|for\s+other\s+uses|disambiguation', text, re.IGNORECASE):
        return 0.05
    # Technical metadata (HSV, sRGB, CIEL, hex triplet, etc.)
    if re.search(r'\b(HSV|sRGB|CIEL|Hex\s+triplet|Colour\s+coordinates?)\b', text, re.IGNORECASE):
        return 0.05

    # 6. STRUCTURE — is it a sentence?
    # Good: starts with capital/Devanagari, ends with punctuation, has verb+subject
    starts_ok = text[0].isupper() or _is_devanagari(text[0])
    ends_punct = text[-1] in f'.!?{_DANDA}'

    # Verb detection: English verbs OR Hindi/Hinglish verbs
    text_lower = text.lower()
    has_verb = bool(re.search(
        r'\b(is|are|was|were|has|have|can|will|do|does|'
        r'make|cook|bake|write|create|learn|use|provide|'
        r'convert|carry|travel|cause|sell|run|go|come)\b',
        text_lower,
    )) or any(v in text_lower for v in _HINDI_VERBS) or \
        any(v in text_lower for v in _HINGLISH_VERBS)

    # Subject detection: generic content words (3+ words not stopwords)
    _STOPWORDS = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'has', 'have', 'had',
        'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may',
        'might', 'shall', 'can', 'to', 'of', 'in', 'for', 'on', 'with',
        'at', 'by', 'from', 'as', 'into', 'about', 'between', 'through',
        'के', 'की', 'का', 'है', 'हैं', 'और', 'में', 'से', 'को', 'पर',
        'एक', 'यह', 'वह', 'तो', 'भी', 'ही', 'ने', 'नहीं', 'या', 'तक',
    }
    words_in_text = re.findall(r'\b[a-zA-Z]{3,}\b', text_lower)
    devanagari_words = re.findall(r'[\u0900-\u097F]{2,}', text)
    all_words = words_in_text + devanagari_words
    content_words = [w for w in all_words if w.lower() not in _STOPWORDS]
    has_subject = len(content_words) >= 3

    if starts_ok and ends_punct:
        score += 0.15
    if has_verb:
        score += 0.1
    if has_subject:
        score += 0.05

    # Penalize high capital-word ratio (navigation menus, titles)
    words = text.split()
    if len(words) > 5:
        capital_words = sum(1 for w in words if len(w) > 1 and (w[0].isupper() or _is_devanagari(w[0])))
        capital_ratio = capital_words / len(words)
        if capital_ratio > 0.6:
            score -= 0.3

    # Penalize non-sentence content (no punctuation in long text)
    if not re.search(f'[.!?{_DANDA}]', text) and len(text) > 100:
        score -= 0.2

    # 6. RELEVANCE — word overlap with query
    if query:
        # Support both Latin and Devanagari query words
        q_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', query.lower()))
        q_words |= set(re.findall(r'[\u0900-\u097F]{2,}', query))
        stop = {'what', 'which', 'where', 'when', 'how', 'who', 'why',
                'is', 'are', 'the', 'and', 'for', 'that', 'this',
                'with', 'you', 'can', 'tell', 'about', 'does', 'do',
                'have', 'has', 'was', 'were', 'will', 'would', 'make',
                'write', 'create', 'build', 'explain', 'teach', 'learn',
                'क्या', 'है', 'कैसे', 'कब', 'कहाँ', 'कौन', 'क्यों'}
        q_words -= stop
        if q_words:
            t_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', text_lower))
            t_words |= set(re.findall(r'[\u0900-\u097F]{2,}', text))
            overlap = q_words & t_words
            if len(overlap) == 0 and len(q_words) >= 2:
                score -= 0.3  # No overlap with query = likely unrelated
            elif overlap:
                score += min(0.2, len(overlap) / len(q_words) * 0.2)

    return max(0.0, min(1.0, score))
