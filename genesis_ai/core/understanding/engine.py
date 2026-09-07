"""Understanding engine for extracting structured intent from user input.

Uses regex patterns and keyword matching to classify user messages
into intent, task type, entities, constraints, and complexity levels.
Supports English, Hindi, and Hinglish input patterns.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from genesis_ai.database.db import DatabaseManager


@dataclass
class UnderstandingResult:
    """Structured representation of what the user wants."""

    intent: str
    task_type: str
    entities: dict = field(default_factory=dict)
    constraints: list = field(default_factory=list)
    output_type: str = "text"
    context_needed: bool = False
    research_needed: bool = False
    complexity: str = "simple"
    domain: str = "general"
    sub_tasks: list = field(default_factory=list)
    raw_message: str = ""


# ── Intent patterns ────────────────────────────────────────────

_CODE_CREATE_KEYWORDS = re.compile(
    r'\b(create|write|code|build|program|script|make|develop|design|implement|'
    r'banao|likho|banayo|tayar|develop|setup|setup|setup karo)\b',
    re.IGNORECASE,
)

_RESEARCH_KEYWORDS = re.compile(
    r'\b(what is|who is|how to|when did|where is|which|define|tell me about|'
    r'kya hai|kaun hai|kaise|kab|kahan|kaun sa|jankari|info|information|'
    r'explain me|batao|samjhao)\b',
    re.IGNORECASE,
)

_EXPLAIN_KEYWORDS = re.compile(
    r'\b(explain|describe|elaborate|clarify|break down|how does|why does|'
    r'samjhao|batao|samjha|vistar se|detail me|pur explain|pur tarah)\b',
    re.IGNORECASE,
)

_COMPARE_KEYWORDS = re.compile(
    r'\b(compare|vs|versus|difference between|better|worse|pros and cons|'
    r'kon sa achha|kis ka better|compare karo|difference|alag)\b',
    re.IGNORECASE,
)

_FIX_KEYWORDS = re.compile(
    r'\b(fix|debug|solve|repair|error|issue|problem|bug|troubleshoot|'
    r'theek|sudhar|fix karo|solve karo|problem hai|error aa raha)\b',
    re.IGNORECASE,
)

_OPTIMIZE_KEYWORDS = re.compile(
    r'\b(optimize|improve|enhance|speed up|make faster|efficient|'
    r'better banao|optimize karo|fast karo)\b',
    re.IGNORECASE,
)

_ANALYZE_KEYWORDS = re.compile(
    r'\b(analyze|analyse|evaluate|assess|review|audit|inspect|'
    r'check karo|parakh|review karo)\b',
    re.IGNORECASE,
)

_SUMMARIZE_KEYWORDS = re.compile(
    r'\b(summarize|summary|short me|brief|concise|nimn|saar|'
    r'summary do|short me batao)\b',
    re.IGNORECASE,
)

_LIST_KEYWORDS = re.compile(
    r'\b(list|enumerate|show all|give me all|top \d+|best \d+|'
    r'sari cheezein|puri list)\b',
    re.IGNORECASE,
)

_TRANSLATE_KEYWORDS = re.compile(
    r'\b(translate|anuvad|tarjuma|hindi me|english me|marathi me|'
    r'convert language)\b',
    re.IGNORECASE,
)


# ── Task type patterns ─────────────────────────────────────────

_TASK_TYPE_PATTERNS = {
    "code": re.compile(
        r'\b(code|program|script|function|class|api|endpoint|database|'
        r'algorithm|data structure|compiler|interpreter|binary|hex|'
        r'python|javascript|java|c\+\+|rust|go|typescript|ruby|php|'
        r'sql|html|css|react|angular|vue|node|django|flask|fastapi|'
        r'pytorch|tensorflow|machine learning|deep learning|neural|'
        r'banao|likho|program|script|code)\b',
        re.IGNORECASE,
    ),
    "factual": re.compile(
        r'\b(what is|who is|when|where|which|is there|does|can|has|have|'
        r'kya hai|kaun hai|kab|kahan|kitna|kitne)\b',
        re.IGNORECASE,
    ),
    "creative": re.compile(
        r'\b(write a story|poem|creative|imagine|fiction|narrative|'
        r'kahani|kavita|story|creative writing|'
        r'metaphor|monologue|prose|lyrics|verse|stanza|sonnet|haiku|ode|limerick|'
        r'ballad|fable|parable|allegory|myth|legend|satire|parody|'
        r'rap|comedy|humor|joke|riddle|caption|tagline|slogan|'
        r'shazish|ghazal|shayari|kavita|kahani|'
        r'dialogue|script|screenplay|'
        r'rhyme|chant|anthem|jingle|'
        r'tale|saga|chronicle|'
        r'portrait|sketch|painting|illustration|'
        r'tribute|elegy|lament|'
        r'epic|ballad|ode|psalm|'
        r'create a|write a|compose|draft|pen|craft|'
        r'banao|likho|sunao|karo)\b',
        re.IGNORECASE,
    ),
    "analysis": re.compile(
        r'\b(analyze|evaluate|assess|compare|contrast|examine|study|'
        r'research|investigate)\b',
        re.IGNORECASE,
    ),
    "math": re.compile(
        r'\b(calculate|compute|solve equation|math|algebra|calculus|'
        r'geometry|trigonometry|statistics|probability|'
        r'ganit|hisab|count|sum|multiply|divide)\b',
        re.IGNORECASE,
    ),
    "conversation": re.compile(
        r'\b(hi+|hello+|hey+|namaste|namaskar|'
        r'good\s*morning|good\s*evening|good\s*afternoon|'
        r'how\s*are\s*you|how.s\s*it\s*going|what.s\s*up|sup|yo|howdy|'
        r'kaise\s*ho|kya\s*haal|kya\s*hal|kaisa\s*chal|'
        r'sab\s*theek|bhai\s*kya|kya\s*scene|'
        r'bye|goodbye|alvida|take\s*care|phir\s*milenge|'
        r'thanks|thank\s*you|shukriya|dhanyavad|'
        r'theek\s*hai|accha|okay|ok|fine|great|good|badhiya|'
        r'mast|bore|bored|timepass)\b',
        re.IGNORECASE,
    ),
}


# ── Programming language extraction ────────────────────────────

_PROGRAMMING_LANGUAGES = re.compile(
    r'\b(python|javascript|typescript|java|c\+\+|c#|rust|go|golang|'
    r'ruby|php|swift|kotlin|scala|haskell|perl|lua|r|matlab|'
    r'assembly|fortran|cobol|lisp|prolog|clojure|elixir|'
    r'html|css|scss|sass|less|sql|noql|graphql|'
    r'bash|powershell|zsh)\b',
    re.IGNORECASE,
)

_FRAMEWORKS = re.compile(
    r'\b(django|flask|fastapi|spring|rails|laravel|symfony|'
    r'react|angular|vue|svelte|nextjs|nuxtjs|'
    r'pytorch|tensorflow|keras|scikit-learn|pandas|numpy|'
    r'nodejs|express|nestjs|deno|bun|'
    r'docker|kubernetes|terraform|ansible|'
    r'mysql|postgresql|mongodb|redis|sqlite|'
    r'aws|azure|gcp)\b',
    re.IGNORECASE,
)

_PERSON_PATTERNS = re.compile(
    r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b'  # Simple capitalized name pattern
)


# ── Constraint patterns ────────────────────────────────────────

_CONSTRAINT_PATTERNS = {
    "lightweight": re.compile(r'\b(lightweight|light|chota|simple|easy)\b', re.IGNORECASE),
    "advanced": re.compile(r'\b(advanced|complex|detailed|professional|expert)\b', re.IGNORECASE),
    "with_gui": re.compile(r'\b(with gui|gui|graphical|visual|interface|screen|display)\b', re.IGNORECASE),
    "cli_only": re.compile(r'\b(cli|command line|terminal|console)\b', re.IGNORECASE),
    "mobile": re.compile(r'\b(mobile|android|ios|phone|app)\b', re.IGNORECASE),
    "web": re.compile(r'\b(web|website|web app|browser|http)\b', re.IGNORECASE),
    "fast": re.compile(r'\b(fast|quick|turant|jaldi|speed)\b', re.IGNORECASE),
    "secure": re.compile(r'\b(secure|security|safe|protected|encrypted)\b', re.IGNORECASE),
    "test": re.compile(r'\b(test|testing|unit test|integration test|test case)\b', re.IGNORECASE),
    "production": re.compile(r'\b(production|deploy|live|server|hosting)\b', re.IGNORECASE),
}


# ── Domain patterns ────────────────────────────────────────────

_DOMAIN_PATTERNS = {
    "programming": re.compile(
        r'\b(program|code|function|class|variable|loop|array|'
        r'algorithm|debug|compile|run|execute|import|module|package|'
        r'git|github|gitlab|bitbucket|ide|vscode|pycharm)\b',
        re.IGNORECASE,
    ),
    "science": re.compile(
        r'\b(science|physics|chemistry|biology|astronomy|geology|'
        r'experiment|hypothesis|theory|research|lab|laboratory)\b',
        re.IGNORECASE,
    ),
    "mathematics": re.compile(
        r'\b(math|maths|mathematics|algebra|geometry|calculus|'
        r'statistics|probability|number|equation|formula|proof)\b',
        re.IGNORECASE,
    ),
    "history": re.compile(
        r'\b(history|historical|ancient|medieval|modern|'
        r'century|era|dynasty|king|queen|war|revolution)\b',
        re.IGNORECASE,
    ),
    "business": re.compile(
        r'\b(business|marketing|finance|accounting|startup|'
        r'revenue|profit|customer|sales|strategy|management)\b',
        re.IGNORECASE,
    ),
    "health": re.compile(
        r'\b(health|medical|disease|symptom|treatment|'
        r'doctor|medicine|exercise|diet|nutrition)\b',
        re.IGNORECASE,
    ),
}


# ── Output type patterns ───────────────────────────────────────

_OUTPUT_TYPE_PATTERNS = {
    "code": re.compile(
        r'\b(code|program|script|function|class|api|implementation|'
        r'banao|likho|code karo)\b',
        re.IGNORECASE,
    ),
    "explanation": re.compile(
        r'\b(explain|describe|elaborate|why|how does|samjhao|batao)\b',
        re.IGNORECASE,
    ),
    "list": re.compile(
        r'\b(list|enumerate|all|top|best|sari|list do)\b',
        re.IGNORECASE,
    ),
    "comparison": re.compile(
        r'\b(compare|vs|versus|difference|better|worse)\b',
        re.IGNORECASE,
    ),
    "tutorial": re.compile(
        r'\b(tutorial|guide|step by step|walkthrough|learn|seekho)\b',
        re.IGNORECASE,
    ),
}


class UnderstandingEngine:
    """Extracts structured understanding from user input using pattern matching.

    Supports English, Hindi, and Hinglish input. Uses pure regex and keyword
    matching without any ML dependencies.
    """

    def __init__(self, db: DatabaseManager):
        self.db = db

    def understand(self, message: str, conversation_context: list[dict] = None) -> UnderstandingResult:
        """Analyze user message and return structured understanding.

        Args:
            message: The raw user input text.
            conversation_context: Optional list of previous messages for context.

        Returns:
            UnderstandingResult with classified intent, entities, constraints, etc.
        """
        result = UnderstandingResult(intent="unknown", task_type="unknown", raw_message=message)
        cleaned = self._preprocess(message)

        result.intent = self._detect_intent(cleaned)
        result.task_type = self._detect_task_type(cleaned)
        result.entities = self._extract_entities(cleaned)
        result.constraints = self._extract_constraints(cleaned)
        result.output_type = self._detect_output_type(cleaned, result.intent)
        result.context_needed = self._needs_context(cleaned, conversation_context)
        result.research_needed = self._needs_research(cleaned, result.intent, result.task_type)
        result.domain = self._detect_domain(cleaned)
        result.sub_tasks = self._decompose_sub_tasks(cleaned, result.intent, result.task_type)
        result.complexity = self._assess_complexity(result)

        return result

    def _preprocess(self, message: str) -> str:
        """Normalize and clean the input message."""
        message = message.strip()
        message = re.sub(r'[!?]{2,}', '!', message)
        message = re.sub(r'\.{2,}', '.', message)
        return message

    def _detect_intent(self, message: str) -> str:
        """Determine the primary intent of the user message."""
        scores = {
            "create": len(_CODE_CREATE_KEYWORDS.findall(message)),
            "research": len(_RESEARCH_KEYWORDS.findall(message)),
            "explain": len(_EXPLAIN_KEYWORDS.findall(message)),
            "compare": len(_COMPARE_KEYWORDS.findall(message)),
            "fix": len(_FIX_KEYWORDS.findall(message)),
            "optimize": len(_OPTIMIZE_KEYWORDS.findall(message)),
            "analyze": len(_ANALYZE_KEYWORDS.findall(message)),
            "summarize": len(_SUMMARIZE_KEYWORDS.findall(message)),
            "list": len(_LIST_KEYWORDS.findall(message)),
            "translate": len(_TRANSLATE_KEYWORDS.findall(message)),
        }

        if not any(scores.values()):
            return "research"

        return max(scores, key=scores.get)

    def _detect_task_type(self, message: str) -> str:
        """Classify the type of task the user is requesting."""
        scores = {}
        for task_type, pattern in _TASK_TYPE_PATTERNS.items():
            scores[task_type] = len(pattern.findall(message))

        if not any(scores.values()):
            return "factual"

        return max(scores, key=scores.get)

    def _extract_entities(self, message: str) -> dict:
        """Extract named entities from the message."""
        entities = {}

        langs = _PROGRAMMING_LANGUAGES.findall(message)
        if langs:
            entities["languages"] = list(set(lang.lower() for lang in langs))

        frameworks = _FRAMEWORKS.findall(message)
        if frameworks:
            entities["frameworks"] = list(set(f.lower() for f in frameworks))

        persons = _PERSON_PATTERNS.findall(message)
        if persons:
            entities["persons"] = list(set(persons))

        topics = self._extract_topics(message)
        if topics:
            entities["topics"] = topics

        return entities

    def _extract_topics(self, message: str) -> list[str]:
        """Extract topic phrases from the message."""
        topics = []
        topic_patterns = [
            r'about\s+([A-Za-z\s]+?)(?:\s+and|\s+or|\s+\?|$)',
            r'of\s+([A-Za-z\s]+?)(?:\s+and|\s+or|\s+\?|$)',
            r'on\s+([A-Za-z\s]+?)(?:\s+and|\s+or|\s+\?|$)',
            r'regarding\s+([A-Za-z\s]+?)(?:\s+and|\s+or|\s+\?|$)',
            r'ke\s+baar(?:e)?\s+me\s+([A-Za-z\s]+?)(?:\s+and|\s+or|\s+\?|$)',
        ]
        for pattern in topic_patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            for m in matches:
                cleaned = m.strip()
                if len(cleaned) > 2 and cleaned.lower() not in {'the', 'a', 'an', 'this', 'that'}:
                    topics.append(cleaned)
        return list(set(topics))

    def _extract_constraints(self, message: str) -> list[str]:
        """Extract user constraints from the message."""
        constraints = []
        for constraint_name, pattern in _CONSTRAINT_PATTERNS.items():
            if pattern.search(message):
                constraints.append(constraint_name)
        return constraints

    def _detect_output_type(self, message: str, intent: str) -> str:
        """Determine what kind of output the user expects."""
        if intent == "create":
            return "code"
        if intent == "explain":
            return "explanation"
        if intent == "compare":
            return "comparison"

        for output_type, pattern in _OUTPUT_TYPE_PATTERNS.items():
            if pattern.search(message):
                return output_type

        return "text"

    def _needs_context(self, message: str, context: list[dict] = None) -> bool:
        """Determine if conversation context is needed to answer."""
        context_indicators = re.compile(
            r'\b(this|that|it|previous|last time|earlier|phir|fir|'
            r'uske baad|woh|yeh|usme|isme|same|again|dobara)\b',
            re.IGNORECASE,
        )
        if context_indicators.search(message):
            return True
        if context and len(context) > 0:
            follow_up = re.compile(
                r'\b(and|also|plus|more|another|next|then|aur|bhi|phir)\b',
                re.IGNORECASE,
            )
            if follow_up.search(message):
                return True
        return False

    def _needs_research(self, message: str, intent: str, task_type: str) -> bool:
        """Determine if internet research is needed to answer."""
        if intent in ("research", "analyze"):
            return True
        if task_type == "factual" and intent != "create":
            return True
        recent_pattern = re.compile(
            r'\b(latest|recent|current|now|today|abhi|'
            r'updated|newest|modern|abhi)\b',
            re.IGNORECASE,
        )
        if recent_pattern.search(message):
            return True
        return False

    def _detect_domain(self, message: str) -> str:
        """Identify the subject domain of the message."""
        scores = {}
        for domain, pattern in _DOMAIN_PATTERNS.items():
            scores[domain] = len(pattern.findall(message))

        if not any(scores.values()):
            return "general"

        return max(scores, key=scores.get)

    def _decompose_sub_tasks(self, message: str, intent: str, task_type: str) -> list[str]:
        """Break the message into sub-tasks where applicable."""
        sub_tasks = []

        if intent == "create":
            sub_tasks.append("define_requirements")
            if task_type == "code":
                sub_tasks.extend(["design_architecture", "write_code", "test_code"])
            else:
                sub_tasks.append("generate_output")

        elif intent == "research":
            sub_tasks.extend(["identify_question", "gather_information", "synthesize_answer"])

        elif intent == "explain":
            sub_tasks.extend(["identify_concept", "gather_details", "structure_explanation"])

        elif intent == "compare":
            sub_tasks.extend(["identify_items", "gather_attributes", "compare_attributes", "summarize_comparison"])

        elif intent == "fix":
            sub_tasks.extend(["identify_error", "diagnose_cause", "propose_solution", "verify_fix"])

        elif intent == "optimize":
            sub_tasks.extend(["analyze_current", "identify_bottlenecks", "propose_improvements"])

        elif intent == "analyze":
            sub_tasks.extend(["gather_data", "apply_analysis", "interpret_results"])

        elif intent == "summarize":
            sub_tasks.extend(["read_content", "extract_key_points", "generate_summary"])

        elif intent == "list":
            sub_tasks.extend(["identify_category", "gather_items", "format_list"])

        elif intent == "translate":
            sub_tasks.extend(["identify_source_lang", "identify_target_lang", "translate_text"])

        else:
            sub_tasks.append("process_query")

        return sub_tasks

    def _assess_complexity(self, result: UnderstandingResult) -> str:
        """Assess overall complexity based on multiple factors."""
        score = 0

        if len(result.sub_tasks) > 4:
            score += 3
        elif len(result.sub_tasks) > 2:
            score += 2
        elif len(result.sub_tasks) > 1:
            score += 1

        if result.research_needed:
            score += 2

        if result.context_needed:
            score += 1

        entity_count = sum(len(v) for v in result.entities.values() if isinstance(v, list))
        if entity_count > 3:
            score += 2
        elif entity_count > 1:
            score += 1

        if len(result.constraints) > 2:
            score += 1

        if result.intent in ("optimize", "analyze", "compare"):
            score += 1

        if score >= 6:
            return "complex"
        elif score >= 3:
            return "moderate"
        return "simple"
