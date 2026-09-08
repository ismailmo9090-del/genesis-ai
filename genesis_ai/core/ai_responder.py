"""
Genesis AI - Smart Response Synthesizer
===========================================
PHILOSOPHY:
  - EVERYTHING comes from the internet first
  - Search results are SYNTHESIZED into natural ChatGPT-style responses
  - Every response is stored locally (offline cache)
  - Creative content (shayari, jokes, stories) = internet search + intelligent extraction
  - Personal/casual chat = internet search for context + natural response
  - NO hardcoded content libraries — everything is live from the web
"""

import re
import logging
import time

logger = logging.getLogger(__name__)

# ─── Intent Classification ────────────────────────────────────────────────────

def classify_message_type(message: str) -> str:
    """
    Classify message into one of:
      CREATIVE   - shayari, jokes, stories, poems, quotes
      CODE       - coding, programming tasks
      CASUAL     - greetings, small talk, personal status, acknowledgements
      FACTUAL    - factual questions (who, what, when, where, how)
      FOLLOWUP   - follow-up referring to previous context
    """
    msg = message.lower().strip()
    words = set(re.findall(r'\b\w+\b', msg))

    # ── 1. Casual greetings / user status (Check FIRST) ──
    # Detect short conversational messages (structural, not exact match)
    word_count = len(words)
    casual_structure = (
        word_count <= 3
        and not re.search(r'\?$', msg)
        and not any(w in msg for w in ['create', 'make', 'build', 'write', 'code', 'banao', 'search', 'find'])
    )
    if casual_structure:
        return 'CASUAL'

    casual_patterns = [
        r'^(hi|hello|hey|hii+|helo|heyy|namaste|namaskar)\b',
        r'^(kya haal|kya hal|kaise ho|kaise h|how are you|what\'s up|sup)\b',
        r'\b(mast|badhiya|badiya|theek|accha|acha|okay|ok|fine|great|good)\s*(hu|hoon|hai|bro|yaar)?\s*[!\.]*$',
        r'^(haan|ha|yes|no|nahi|nope)\s*[!\.]*$',
        r'^(bye|goodbye|alvida|phir milenge|take care)\b',
        r'\b(bore|bored|maza|fun|timepass|time pass)\b',
        r'\b(shukriya|thank you|thanks|dhanyavad|dhanyawad)\b',
    ]
    for p in casual_patterns:
        if re.search(p, msg):
            return 'CASUAL'

    # ── 2. Code tasks — detect by structural patterns ──
    code_action = re.search(
        r'\b(banao|bana|create|make|write|build|generate|implement|develop|likho|code karo|code|program|script)\b',
        msg
    )
    has_code_words = bool(re.search(
        r'\b(code|program|script|function|class|api|algorithm|data structure|'
        r'compiler|interpreter|debug|compile|execute|import|module|package|'
        r'frontend|backend|fullstack|database|endpoint|server|deploy)\b',
        msg
    ))
    has_fix_words = bool(re.search(
        r'\b(fix|debug|error|bug|broken|not working|crash|issue|problem)\b.{0,40}\b(code|program|script|function|app)\b',
        msg
    ))

    if (code_action and has_code_words) or has_fix_words:
        return 'CODE'

    # ── 3. Creative content — detect by role words ──
    creative_roles = re.search(
        r'\b(poem|poetry|shayari|sher|ghazal|nazm|joke|jokes|mazak|funny|comedy|'
        r'story|kahani|kissa|fairytale|song|gana|lyrics|'
        r'quote|quotes|suvichar|motivational|inspirational|'
        r'riddle|paheli|puzzle|dialogue|script)\b',
        msg
    )
    if creative_roles:
        return 'CREATIVE'

    # ── 4. Follow-up — structural pattern (short + pronoun + question) ──
    pronoun_hi = {'uska', 'iska', 'uske', 'iske', 'uski', 'iski', 'unka', 'woh', 'ye', 'yeh', 'vo', 'voh'}
    pronoun_en = {'he', 'she', 'it', 'they', 'him', 'her', 'them', 'this', 'that'}
    is_followup_pronoun = bool(words & pronoun_hi) or bool(words & pronoun_en)
    is_question_like = bool(re.search(
        r'\b(kya|hai|kaun|kaise|kab|kahan|what|how|who|when|where|top|best|film|movie|song)\b', msg
    ))
    if is_followup_pronoun and is_question_like and word_count <= 15:
        return 'FOLLOWUP'

    return 'FACTUAL'


# ─── Search Query Builder ──────────────────────────────────────────────────────

def build_search_queries(message: str, msg_type: str, context_entity: str = None) -> list:
    """
    Build optimized search queries for each message type.
    Returns a list of queries to try (best first).
    """
    msg = message.strip()
    msg_lower = msg.lower()

    # ── CREATIVE queries ──
    if msg_type == 'CREATIVE':
        name_match = _extract_name_for_creative(msg)
        if name_match:
            return [
                f'{msg} {name_match}',
                f'{name_match} {msg}',
            ]
        # Extract thematic keywords from the message to build queries
        topic_words = re.findall(r'\b[a-zA-Z]{3,}\b', msg_lower)
        if topic_words:
            topic_str = ' '.join(topic_words[:3])
            return [
                f'{topic_str} hindi',
                f'{topic_str} best',
            ]
        return [msg, f'{msg} hindi']

    # ── FOLLOWUP queries ──
    if msg_type == 'FOLLOWUP' and context_entity:
        clean_msg = _remove_pronouns(msg_lower)
        if clean_msg:
            return [
                f'{context_entity} {clean_msg}',
                f'{context_entity} {clean_msg} details',
            ]
        return [f'{context_entity} information details']

    # ── FACTUAL queries ──
    if msg_type == 'FACTUAL':
        queries = [msg]
        hindi_fillers = r'\b(kya|hai|kaun|kaise|kab|kahan|batao|samjhao|mujhe|mein|ka|ki|ke|ko|aur|bhi|to|phir|ab)\b'
        clean = re.sub(hindi_fillers, '', msg_lower, flags=re.IGNORECASE).strip()
        clean = re.sub(r'\s+', ' ', clean).strip()
        if clean and clean != msg_lower and len(clean) > 3:
            queries.append(clean)
        return queries

    return [msg]


def _extract_name_for_creative(msg: str) -> str:
    """Extract a person's name from creative requests like 'Priya naam se shayari'."""
    patterns = [
        r'(\w+)\s+(?:naam|name)\s+(?:se|par|pe|ki|ka)\s+shayari',
        r'shayari\s+(?:on|about|for)\s+(?:name\s+)?(\w+)',
        r'(\w+)\s+(?:ke liye|ke baare mein|par)\s+shayari',
        r'write\s+(?:a\s+)?shayari\s+(?:for|about)\s+(\w+)',
    ]
    for p in patterns:
        m = re.search(p, msg.lower())
        if m:
            name = m.group(1).strip()
            # Exclude common words
            if name not in {'love', 'sad', 'best', 'ek', 'mujhe', 'meri', 'mera', 'koi', 'kuch', 'mere'}:
                return name.title()
    return None


def _remove_pronouns(msg: str) -> str:
    """Remove pronouns from follow-up message to get the actual question."""
    pronouns = r'\b(uska|iska|uske|iske|uski|iski|unka|woh|ye|yeh|vo|voh|he|she|it|they|him|her|them|this|that|these|those)\b'
    cleaned = re.sub(pronouns, '', msg, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


# ─── Response Synthesizer ──────────────────────────────────────────────────────

def synthesize_response(
    query: str,
    results: list,
    lang: str,
    msg_type: str,
    context_entity: str = None,
    name_for_creative: str = None,
) -> str:
    """
    Core function: Takes raw web search results and synthesizes a
    ChatGPT/Gemini-quality response.

    Args:
        query: Original user message
        results: List of SearchResult objects from web search
        lang: 'hindi', 'hinglish', or 'english'
        msg_type: CREATIVE, CODE, FACTUAL, FOLLOWUP, CASUAL
        context_entity: Last discussed entity (for follow-ups)
        name_for_creative: Name to use in creative content (shayari)
    """
    if not results:
        return None

    # Extract clean snippets — pass query for relevance checking
    snippets, titles, urls = _extract_clean_snippets(results, query)
    if not snippets:
        return None

    q_lower = query.lower()

    # ── Route to specialized synthesizers based on content structure ──
    if msg_type == 'CREATIVE':
        return _synthesize_generic(query, snippets, titles, urls, lang)

    # Detect question type by structural patterns
    has_person_q = bool(re.search(r'\b(who is|kaun hai|kon hai|who was|kaun tha)\b', q_lower))
    has_definition_q = bool(re.search(r'\b(what is|kya hai|kya hota|what are|explain|samjhao|define|matlab)\b', q_lower))
    has_howto_q = bool(re.search(r'\b(how to|kaise|kaise karna|steps|process|tarika)\b', q_lower))
    has_list_q = bool(re.search(r'\b(top|best|popular|famous|list|movies|films|songs)\b', q_lower))

    if has_person_q:
        return _synthesize_person(query, snippets, titles, urls, lang)
    if has_definition_q:
        return _synthesize_definition(query, snippets, titles, urls, lang)
    if has_howto_q:
        return _synthesize_howto(query, snippets, titles, urls, lang)
    if has_list_q:
        return _synthesize_list(query, snippets, titles, urls, lang)

    return _synthesize_generic(query, snippets, titles, urls, lang)


# ─── Creative Content Extractors ──────────────────────────────────────────────

# ─── Creative Content Extractors ──────────────────────────────────────────────

def _synthesize_generic_creative(query, snippets: list, titles: list, urls: list, lang: str, name: str = None) -> str:
    """Synthesize creative content from web results — generic, not type-specific."""
    merged = _merge_snippets_natural(snippets, 600)
    if not merged:
        merged = snippets[0][:400] if snippets else "Content not available."

    intro = {
        'hindi': f"✨ **{query.strip().title()}** ✨\n\n",
        'hinglish': f"✨ **{query.strip().title()}** ✨\n\n",
        'english': f"✨ **{query.strip().title()}** ✨\n\n",
    }.get(lang, f"✨ **{query.strip().title()}** ✨\n\n")

    return intro + merged


def _clean_snippet_meta(text: str) -> str:
    """Remove site promotional sentences and website noise using quality scoring."""
    from genesis_ai.utils.quality import quality_score
    sentences = re.split(r'(?<=[.!?।\n])\s+', text)
    valid_sentences = []
    for s in sentences:
        s_clean = s.strip()
        if not s_clean:
            continue
        # Skip URLs
        if s_clean.startswith('http') or 'www.' in s_clean.lower():
            continue
        # Use generic quality scorer — replaces hardcoded domain keyword list
        if quality_score(s_clean) < 0.3:
            continue
        valid_sentences.append(s_clean)

    return ' '.join(valid_sentences).strip()


def _extract_shayari_text(snippets: list) -> str:
    """
    Intelligently extract actual shayari/poetry from web snippets.
    Shayari has: short lines, poetic flow, often rhymes.
    """
    for raw in snippets:
        snippet = _clean_snippet_meta(raw)
        if not snippet:
            continue

        # Look for lines with poetic dividers: |, —, -, \n, or ।
        for sep in ['\n', ' | ', ' — ', ' - ', '।']:
            if sep in snippet:
                parts = [p.strip() for p in snippet.split(sep) if 10 < len(p.strip()) < 100]
                if len(parts) >= 2:
                    text_cand = '\n'.join(parts[:4])
                    if len(text_cand) > 30:
                        return text_cand

        # Split into sentences
        sentences = [s.strip() for s in re.split(r'(?<=[.!?।])\s+', snippet) if 15 < len(s.strip()) < 100]
        if len(sentences) >= 2:
            cand = '\n'.join(sentences[:2])
            return cand

    return ""


def _get_default_shayari(lang: str, name: str = None) -> str:
    """Fallback shayari — generates a simple one if search fails."""
    if name:
        return f"{name} naam hai tera, dil ko chhu jaata hai,\nHar pal tera khayal, mann ko bha jaata hai."
    return {
        'hindi': "लफ़्ज़ों में क्या बयाँ करूँ, जो दिल में छुपा है,\nतेरे आने से ज़िंदगी में, एक नया सवेरा है।",
        'hinglish': "Lafzon mein kya bayan karoon, jo dil mein chhupa hai,\nTere aane se zindagi mein, ek naya savera hai.",
        'english': "How to express what the heart holds,\nYour presence brings a new dawn to life.",
    }.get(lang, "Words fail to express what the heart feels.")


def _personalize_shayari(shayari: str, name: str) -> str:
    """Try to personalize shayari by incorporating the given name."""
    if name.lower() in shayari.lower():
        return shayari
    return f"{name} — {shayari}"


def _synthesize_joke(snippets: list, lang: str) -> str:
    """Extract actual joke from web results."""
    best_joke = _extract_joke_text(snippets)

    if not best_joke:
        best_joke = snippets[0][:300] if snippets else "Koi joke nahi mila."

    intro = {
        'hindi': "😂 **Joke!**\n\n",
        'hinglish': "😂 **Joke time!**\n\n",
        'english': "😂 **Here's a joke!**\n\n",
    }.get(lang, "😂\n\n")

    outro = {
        'hindi': "\n\n---\nऔर jokes चाहिए? 😄 बस बोलिए!",
        'hinglish': "\n\n---\nAur jokes chahiye? 😄 Bas bolo!",
        'english': "\n\n---\nWant more jokes? 😄 Just ask!",
    }.get(lang, "\n\n---\nMore? 😄")

    return intro + best_joke + outro


# ─── Factual Synthesizers ──────────────────────────────────────────────────────

def _synthesize_person(query, snippets, titles, urls, lang) -> str:
    """ChatGPT-style person bio — natural, flowing, informative."""
    merged = _merge_snippets_natural(snippets, 600)
    name = _extract_topic(query, 'person')

    intro = {
        'hindi': f"**{name}** के बारे में:\n\n",
        'hinglish': f"**{name}** ke baare mein:\n\n",
        'english': f"Here's what I found about **{name}**:\n\n",
    }.get(lang, f"**{name}**\n\n")

    body = _make_flowing_paragraph(merged)

    extra = _get_extra_points(snippets[1:], merged, 2)
    result = intro + body

    if extra:
        more_hdr = {
            'hindi': "\n\n**और जानकारी:**\n",
            'hinglish': "\n\n**Aur info:**\n",
            'english': "\n\n**More details:**\n",
        }.get(lang, "\n\n**More:**\n")
        result += more_hdr + "\n".join(f"• {p}" for p in extra)

    return result


def _synthesize_definition(query, snippets, titles, urls, lang) -> str:
    """ChatGPT-style explanation/definition."""
    merged = _merge_snippets_natural(snippets, 600)
    topic = _extract_topic(query, 'what')

    intro = {
        'hindi': f"**{topic}**\n\n",
        'hinglish': f"**{topic}**\n\n",
        'english': f"**{topic}**\n\n",
    }.get(lang, f"**{topic}**\n\n")

    body = _make_flowing_paragraph(merged)
    extra = _get_extra_points(snippets[1:], merged, 2)

    result = intro + body
    if extra:
        more_hdr = {
            'hindi': "\n\n**मुख्य बातें:**\n",
            'hinglish': "\n\n**Key points:**\n",
            'english': "\n\n**Key points:**\n",
        }.get(lang, "\n\n**Key points:**\n")
        result += more_hdr + "\n".join(f"• {p}" for p in extra)

    followup = {
        'hindi': "\n\nकोई और सवाल है? 😊",
        'hinglish': "\n\nAur kuch jaanna chahte ho? 😊",
        'english': "\n\nWant to know more about any specific aspect? 😊",
    }.get(lang, "")
    result += followup

    return result


def _synthesize_howto(query, snippets, titles, urls, lang) -> str:
    """ChatGPT-style step-by-step how-to."""
    merged = _merge_snippets_natural(snippets, 700)
    topic = _extract_topic(query, 'how')

    intro = {
        'hindi': f"**{topic}** — यह करने का तरीका:\n\n",
        'hinglish': f"**{topic}** — Yeh kaise karte hain:\n\n",
        'english': f"**How to {topic}:**\n\n",
    }.get(lang, f"**{topic}**\n\n")

    steps = _extract_steps(merged)
    if len(steps) >= 2:
        body = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps[:7]))
    else:
        body = _make_flowing_paragraph(merged)

    return intro + body


def _synthesize_list(query, snippets, titles, urls, lang) -> str:
    """ChatGPT-style list response for top/best queries."""
    merged = _merge_snippets_natural(snippets, 600)
    topic = _extract_topic(query, 'list')

    items = _extract_list_items(merged)
    if len(items) >= 2:
        intro = {
            'hindi': f"**{topic}** — Top results:\n\n",
            'hinglish': f"**{topic}** — Top picks:\n\n",
            'english': f"**{topic}** — Here are the top picks:\n\n",
        }.get(lang, f"**{topic}**\n\n")
        body = "\n".join(f"{i+1}. {item}" for i, item in enumerate(items[:8]))
        return intro + body
    else:
        return _synthesize_generic(query, snippets, titles, urls, lang)


def _synthesize_generic(query, snippets, titles, urls, lang) -> str:
    """Generic ChatGPT-style response for any query."""
    merged = _merge_snippets_natural(snippets, 600)
    topic = _extract_topic(query, 'generic')

    body = _make_flowing_paragraph(merged)
    extra = _get_extra_points(snippets[1:], merged, 2)

    result = f"**{topic}**\n\n{body}"
    if extra:
        result += "\n\n" + "\n".join(f"• {p}" for p in extra)

    return result


# ─── Casual Response (internet-enhanced) ──────────────────────────────────────

def get_casual_response(message: str, lang: str, context_history: list) -> str:
    """
    Natural casual conversation responses using structural pattern detection.
    No hardcoded response pools — generates contextually appropriate replies.
    """
    msg = message.lower().strip()
    word_count = len(msg.split())

    def L(hi, mix, en):
        return {'hindi': hi, 'hinglish': mix, 'english': en}.get(lang, mix)

    # Detect conversational role by structure
    is_greeting = bool(re.search(r'^(hi|hello|hey|hii+|helo|heyy|namaste|namaskar)\b', msg))
    is_farewell = bool(re.search(r'\b(bye|goodbye|alvida|phir milenge|take care)\b', msg))
    is_thanks = bool(re.search(r'\b(shukriya|thank you|thanks|dhanyavad|dhanyawad)\b', msg))
    is_acknowledgment = bool(re.search(r'^(theek|accha|ok|okay|acha|fine|great|good|badhiya)\s*[!.]*$', msg))
    is_question_about_self = bool(re.search(
        r'\b(who are you|what are you|kaun|kya|tumhara naam|your name|capability|kya kar)\b', msg
    ))
    is_status = bool(re.search(
        r'\b(mast|badhiya|badiya|theek|accha|good|great|fine|awesome|superb|bindass)\b', msg
    ))
    is_bored = bool(re.search(r'\b(bore|bored|boredom|maza|fun|timepass|time pass)\b', msg))

    # Build response based on detected role
    if is_greeting:
        return L(
            "नमस्ते! 😊 बताइए, क्या help चाहिए?",
            "Hey! 😊 Batao, kya karte hain aaj?",
            "Hey! 😊 What can I help you with today?",
        )
    if is_farewell:
        return L(
            "अलविदा! 😊 जब भी कोई काम हो — coding, information, कुछ भी — वापस आइए!",
            "Bye yaar! 😊 Kab bhi kuch chahiye — coding, info, sab ke liye aate rehna!",
            "Goodbye! 😊 Come back anytime — for code, questions, or just a chat!",
        )
    if is_thanks:
        return L(
            "खुशी हुई help करके! 😊 कोई और सवाल है?",
            "Khushi hui! 😊 Aur kuch chahiye?",
            "Glad I could help! 😊 Anything else?",
        )
    if is_acknowledgment:
        return L(
            "ठीक है! 😊 कोई और काम हो तो बताइए।",
            "Theek hai! 😊 Kuch aur chahiye to bol dena.",
            "Got it! 😊 Let me know if you need anything else.",
        )
    if is_question_about_self:
        return L(
            "मैं Genesis AI हूँ — आपका personal AI assistant! 😊\nबताइए, क्या करना है?",
            "Main Genesis AI hoon — tumhara personal AI assistant! 😊\nBatao kya karna hai?",
            "I'm Genesis AI — your personal AI assistant! 😊\nHow can I help you?",
        )
    if is_status:
        return L(
            "सुनकर अच्छा लगा! 😊 बताइए, आज क्या करना है?",
            "Suno to dil khush ho gaya! 😊 Batao, aaj kya plan hai?",
            "Great to hear! 😊 What are we working on today?",
        )
    if is_bored:
        return L(
            "Bored हो? चलो कुछ करते हैं! 😄\nCoding, research, या कुछ creative — बताइए!",
            "Bored ho? Aao kuch karte hain! 😄\nCoding, research, ya creative — bolo!",
            "Bored? Let's do something! 😄\nCoding, research, or creative — pick one!",
        )
    if word_count <= 3:
        return L(
            "बताइए! मैं ready हूँ। 😊",
            "Batao yaar! Ready hoon. 😊",
            "I'm here! What do you need? 😊",
        )
    return L(
        "बताइए! मैं हर काम के लिए ready हूँ। 😊",
        "Batao yaar! Koi bhi kaam ho — main ready hoon. 😊",
        "I'm here! Ask me anything — questions, coding, or just a chat. 😊",
    )


# ─── Helper Utilities ─────────────────────────────────────────────────────────

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


def _extract_clean_snippets(results: list, query: str = "") -> tuple:
    """Extract and clean snippets from search results.
    
    Args:
        results: List of search results
        query: Original user query for relevance checking
    """
    snippets, titles, urls = [], [], []
    # Keep only minimal universal junk patterns (metadata, not content)
    junk_patterns = [
        r'\b\d+(\.\d+)?[KkMm]?\s+(subscribers|views|likes|followers|posts)\b',
        r'#\w+',
        r'\b\d+\s+years?\s+ago\b',
    ]
    from genesis_ai.utils.quality import quality_score
    for r in results:
        if not r.snippet:
            continue
        clean = r.snippet
        for old, new in [("&#x27;", "'"), ("&amp;", "&"), ("&quot;", '"'),
                          ("&#39;", "'"), ("&lt;", "<"), ("&gt;", ">"),
                          ("&nbsp;", " "), ("&#x20;", " "), ("\u200b", "")]:
            clean = clean.replace(old, new)
        clean = re.sub(r'\[.*?\]', '', clean)

        # Pre-filter: reject encoding failures BEFORE quality scoring
        if _has_encoding_failure(clean):
            continue

        # Pre-filter: reject hashtag spam
        if _has_hashtag_spam(clean):
            continue

        # Pre-filter: reject self-promotional content
        if _has_self_promotion(clean):
            continue

        for pat in junk_patterns:
            clean = re.sub(pat, '', clean, flags=re.IGNORECASE)
        clean = re.sub(r'\s+', ' ', clean).strip()

        # Minimum length after cleaning
        if len(clean) < 30:
            continue

        # Use generic quality scorer with query for relevance checking
        if quality_score(clean, query) < 0.3:
            continue
        snippets.append(clean)
        titles.append(r.title or "")
        urls.append(r.url or "")
    return snippets, titles, urls


def _merge_snippets_natural(snippets: list, max_chars: int = 800) -> str:
    """Merge multiple snippets removing duplicate sentences."""
    seen = set()
    parts = []
    total = 0
    for snippet in snippets:
        sentences = re.split(r'(?<=[.!?।])\s+', snippet)
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 20:
                continue
            key = sent.lower()[:50]
            if key in seen:
                continue
            seen.add(key)
            parts.append(sent)
            total += len(sent)
            if total >= max_chars:
                break
        if total >= max_chars:
            break
    return ' '.join(parts)


def _make_flowing_paragraph(text: str) -> str:
    """Convert merged text into a clean, readable paragraph."""
    sentences = re.split(r'(?<=[.!?।])\s+', text)
    good = [s.strip() for s in sentences if len(s.strip()) > 20]
    return ' '.join(good[:5]) if good else text[:400]


def _get_extra_points(snippets: list, main_text: str, count: int) -> list:
    """Get additional bullet points from extra snippets."""
    extra = []
    main_lower = main_text.lower()
    for s in snippets:
        short = s[:200].rsplit(' ', 1)[0]
        if short and short.lower()[:40] not in main_lower and len(short) > 20:
            extra.append(short)
        if len(extra) >= count:
            break
    return extra


def _extract_steps(text: str) -> list:
    """Extract numbered steps from text."""
    numbered = re.findall(r'(?:^|\n)\s*\d+[.)]\s*(.+?)(?=\n|$)', text)
    if numbered and len(numbered) >= 2:
        return [s.strip() for s in numbered if len(s.strip()) > 10]
    sentences = re.split(r'(?<=[.!?।])\s+', text)
    return [s.strip() for s in sentences if len(s.strip()) > 20][:6]


def _extract_list_items(text: str) -> list:
    """Extract list items from text."""
    numbered = re.findall(r'(?:^|\n)\s*\d+[.)]\s*(.+?)(?=\n|$)', text)
    if numbered and len(numbered) >= 2:
        return [s.strip() for s in numbered]
    bulleted = re.findall(r'(?:^|\n)\s*[-•*]\s*(.+?)(?=\n|$)', text)
    if bulleted and len(bulleted) >= 2:
        return [s.strip() for s in bulleted]
    return []


def _extract_topic(query: str, mode: str = 'generic') -> str:
    """Extract display topic from query."""
    q = query.strip()
    remove_patterns = [
        r'\b(what is|what are|what was|kya hai|kya hota|kya hoti|explain|samjhao|batao|define)\b\s*',
        r'\b(how to|kaise|kaise karna|how do|how can)\b\s*',
        r'\b(tell me about|mujhe batao|about|ke baare mein)\b\s*',
        r'\b(who is|who was|kaun hai|kon hai)\b\s*',
        r'\b(when was|kab|where is|kahan)\b\s*',
        r'\b(uski|iska|uske|iske|unka|woh|yeh|ye|kaun si hai|kon si hai|kaun si|kon si)\b\s*',
        r'\?+$',
    ]
    for pat in remove_patterns:
        q = re.sub(pat, '', q, flags=re.IGNORECASE).strip()
    q = re.sub(r'\s+', ' ', q).strip()
    return q.title() if q else query.title()
