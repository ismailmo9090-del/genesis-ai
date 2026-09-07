from dataclasses import dataclass, field
from typing import Dict, List, Optional
import re


@dataclass
class IntentResult:
    intent: str
    confidence: float
    entities: Dict[str, str] = field(default_factory=dict)
    raw_message: str = ""


class IntentEngine:
    def __init__(self):
        self.greeting_patterns = [
            r"\b(hello|hi|hey|hii|heyy|helo|hii+|namaste|namaskar|ram ram|radhe radhe)\b",
            r"\b(good\s*(morning|afternoon|evening|night))\b",
            r"\b(kaise\s*ho|kya\s*haal|kaise\s*ho\s*aap|kaise\s*hain|kaise\s*hain\s*aap)\b",
            r"\b(sup|yo|howdy|how\s*are\s*you)\b",
        ]
        self.task_patterns = [
            r"\b(banao|bana|create|make|write|karo|develop|build|generate|setup|install|deploy)\b",
            r"\b(help|madad|help\s*karo|help\s*me|meri\s*madad)\b",
            r"\b(fix|debug|solve|repair|sudhar|thik\s*karo|resolve)\b",
            r"\b(code|likho|code\s*likho|coding|programming|development)\b",
            r"\b(implement|add|insert|update|modify|change|change\s*karo)\b",
            r"\b(setup|setup\s*karo|configure|configure\s*karo)\b",
        ]
        self.question_patterns = [
            r"\b(kya|kyu|kaise|kab|kitna|kaun|kahan|kitni|kitne|kaisi|kaise|why|how|what|when|where|which|who)\b.*\?",
            r"\b(kya\s*hai|kya\s*hoti|kya\s*karta|explain|samjhao|samjhao\s*mujhe)\b",
            r"\b(diff(ference)?|compare|versus|vs)\b",
            r"\b(weather|samay|time|date|din)\b",
            r"\b(process|working|mechanism|principle)\b.*\?",
            r"^(what|how|why|where|when|who|which)\s+",
            r"\b(kya\s+hai|kya\s+hot[ai]|kaise\s+kaam\s+karta|kaun\s+hai)\b",
            r"\bwhat\s+is\s+\w+",
            r"\w+\s+kya\s+hai",
            r"\b(who|what|how|why|where)\s+is\s+\w+",
            r"\b(who|what|how|why|where)\s+are\s+\w+",
            r"\b(who|what)\s+was\s+\w+",
            r"\btell\s+me\s+about\b",
            r"\bbatao\s+(ki|ke\s+baare|mein)\b",
            r"\b(kitni|kitne|kitna|kaisi|kaise|kaunsi)\b",
            r"\b(hai|hoti|hain|hue|huai|huye)\s*$",
            r"\bbaare\s+mein\s+(batao|samjhao|btata|btata)\b",
            r"\b(paida|paida|paiidda|paaida|janm|janam|born)\b",
            r"\b(kahan|kahaa|kidhar|where)\s+(hue|huai|huye|hai|hain|tha|thi|the)\b",
            r"\b(kab|kabse|when)\s+(hue|huai|huye|hai|hain|tha|thi|the)\b",
        ]
        self.feedback_positive_patterns = [
            r"\b(thanks|thank\s*you|dhanyavaad|shukriya|accha|badhiya|great|awesome|perfect|excellent|wonderful)\b",
            r"\b(sahi\s*hai|theek\s*hai|sahi|bilkul|haan\s*bilkul|nice|good\s*job|well\s*done)\b",
            r"\b(bahut\s*accha|ekdum\s*badhiya|mast|lajawab|zabardast)\b",
        ]
        self.feedback_negative_patterns = [
            r"\b(nahi|nahin|wrong|galat|not\s*working|kaam\s*nahi\s*kar|broken|error|fail)\b",
            r"\b(bakwas|bekar|worst|horrible|terrible|awful)\b",
            r"\b(sahi\s*nahi|theek\s*nahi|ghatiya|sasta|jhol)\b",
        ]
        self.command_patterns = [
            r"\b(stop|ruk|pause|halt|cancel|radd|band\s*karo|close|exit|quit|logout)\b",
            r"\b(clear|saaf|reset|restart|dobara|phir\s*se|start\s*over)\b",
            r"\b(save|bachao|store|rakh|export|download)\b",
            r"\b(run|chala|execute|launch|perform)\b",
        ]
        self.reflection_patterns = [
            r"\b(think|soch|socho|reflect|vichaar|manan|chintan|contemplate)\b",
            r"\b(past|past\s*me|pichle|previous|history|memory|yaad)\b",
            r"\b(learn|seekho|sikhne|improve|better|grow|vixit)\b",
            r"\b(goal|lakshya|aim|purpose|udhesya|mission)\b",
        ]
        self.casual_patterns = [
            r"\b(who\s+are\s+you|what\s+are\s+you|kaun\s+hai\s+tum|kya\s+hai\s+tum|tumhara\s+naam)\b",
            r"\b(what\s+can\s+you\s+do|kya\s+kar\s+sakte|kya\s+kar\s+sakta|tumhara\s+kaam|your\s+capability)\b",
            r"\b(theek\s+hai|accha|ok|okay|acha|alright|fine|good|badhiya|great)\b",
            r"\b(boring|bored|maza|fun|interesting|accha\s+lagta)\b",
        ]
        self.programming_languages = [
            "python", "javascript", "typescript", "java", "c", "c++", "c#",
            "rust", "go", "golang", "ruby", "php", "swift", "kotlin",
            "html", "css", "scss", "sql", "r", "matlab", "perl",
            "scala", "haskell", "elixir", "dart", "lua", "bash", "powershell",
        ]
        self.tools = [
            "git", "docker", "kubernetes", "k8s", "nginx", "apache", "redis",
            "postgresql", "mysql", "mongodb", "sqlite", "elasticsearch",
            "jenkins", "terraform", "ansible", "aws", "azure", "gcp",
            "vscode", "vim", "neovim", "emacs", "intellij", "pycharm",
            "npm", "yarn", "pip", "cargo", "maven", "gradle",
            "webpack", "vite", "esbuild", "rollup", "parcel",
            "pytest", "jest", "mocha", "junit", "selenium",
        ]
        self.file_types = [
            "py", "js", "ts", "java", "c", "cpp", "h", "rs", "go",
            "html", "css", "scss", "json", "yaml", "yml", "toml", "xml",
            "sql", "md", "txt", "csv", "sh", "bat", "ps1", "dockerfile",
            "env", "gitignore", "lock", "config", "ini", "cfg",
        ]
        self.topic_keywords = {
            "web_development": ["web", "website", "frontend", "backend", "api", "rest", "graphql", "http", "server", "client"],
            "data_science": ["data", "ml", "ai", "machine learning", "deep learning", "neural", "model", "dataset", "pandas", "numpy", "tensorflow", "pytorch"],
            "devops": ["deploy", "ci/cd", "pipeline", "container", "docker", "kubernetes", "cloud", "infrastructure"],
            "database": ["database", "db", "sql", "query", "table", "schema", "migration", "orm", "redis", "mongo"],
            "mobile": ["android", "ios", "mobile", "app", "flutter", "react native", "swift", "kotlin"],
            "security": ["security", "auth", "encryption", "token", "jwt", "oauth", "password", "vulnerability"],
            "algorithms": ["algorithm", "data structure", "sorting", "searching", "graph", "tree", "array", "linked list", "stack", "queue"],
            "system_design": ["system design", "architecture", "scalable", "microservices", "distributed", "load balancer", "cache"],
        }

    def classify_intent(self, message: str) -> IntentResult:
        message_lower = message.lower().strip()
        scores: Dict[str, float] = {}
        scores["GREETING"] = self._score_patterns(message_lower, self.greeting_patterns)
        scores["TASK_REQUEST"] = self._score_patterns(message_lower, self.task_patterns)
        scores["QUESTION"] = self._score_patterns(message_lower, self.question_patterns)
        scores["FEEDBACK_POSITIVE"] = self._score_patterns(message_lower, self.feedback_positive_patterns)
        scores["FEEDBACK_NEGATIVE"] = self._score_patterns(message_lower, self.feedback_negative_patterns)
        scores["COMMAND"] = self._score_patterns(message_lower, self.command_patterns)
        scores["REFLECTION"] = self._score_patterns(message_lower, self.reflection_patterns)
        scores["CASUAL"] = self._score_patterns(message_lower, self.casual_patterns)
        if "?" in message and scores["QUESTION"] < 0.3:
            scores["QUESTION"] += 0.3

        # ── "kaise" disambiguation (grammatical, not topic-specific) ──
        # "kaise ho/hain" = greeting (being-verb, referring to listener's state)
        # "kaise hota/banta/chalta hai" = informational (process-verb, how X works)
        if "kaise" in message_lower:
            _GREETING_VERBS = r'(ho|hain|h|ho\s+aap|hain\s+aap)\s*[!.?\s]*$'
            _PROCESS_VERBS = r'(hota|hoti|banta|banti|banate|banati|chalta|chalti|karta|karti|banaya|banaye|kiya|kiye|hoga|hua|hui|kaam|reh|rahe|rahi|sak|sake|pad|pade|ja|jaye|aa|aaye|de|diye|le|liye)'
            is_greeting_kaise = bool(re.search(_GREETING_VERBS, message_lower))
            is_process_kaise = bool(re.search(_PROCESS_VERBS, message_lower))
            if is_greeting_kaise and not is_process_kaise:
                # Boost greeting, suppress question
                scores["GREETING"] = max(scores["GREETING"], 0.6)
                scores["QUESTION"] = max(0.0, scores["QUESTION"] - 0.3)
            elif is_process_kaise:
                # Boost question, suppress greeting
                scores["QUESTION"] = max(scores["QUESTION"], 0.5)
                scores["GREETING"] = max(0.0, scores["GREETING"] - 0.3)
        entities = self._extract_entities(message_lower)
        if entities.get("programming_language") or entities.get("tool") or entities.get("file_type"):
            if scores["TASK_REQUEST"] < 0.5:
                scores["TASK_REQUEST"] += 0.2
        if not scores["QUESTION"] and not scores["TASK_REQUEST"] and not scores["GREETING"]:
            word_count = len(message_lower.split())
            if word_count <= 3:
                scores["CASUAL"] = 0.5
            else:
                scores["CASUAL"] = 0.2
            if scores["CASUAL"] < scores.get("TASK_REQUEST", 0):
                scores["CASUAL"] = 0.0
        if scores["CASUAL"] >= scores.get("QUESTION", 0) and scores["CASUAL"] > 0:
            best_intent = "CASUAL"
            best_score = scores["CASUAL"]
        else:
            best_intent = max(scores, key=scores.get)
            best_score = scores[best_intent]
        if best_score < 0.1:
            best_intent = "CASUAL"
            best_score = max(best_score, 0.1)
        confidence = min(best_score, 1.0)
        if best_intent == "CASUAL" and best_score < 0.3 and scores.get("QUESTION", 0) > 0.5:
            best_intent = "QUESTION"
            confidence = max(scores["QUESTION"], 0.3)
        return IntentResult(
            intent=best_intent,
            confidence=round(confidence, 3),
            entities=entities,
            raw_message=message,
        )

    def _score_patterns(self, text: str, pattern_list: List[str]) -> float:
        score = 0.0
        for pattern in pattern_list:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                score += 0.4 * min(len(matches), 3)
        return min(score, 1.0)

    def _extract_entities(self, text: str) -> Dict[str, str]:
        entities: Dict[str, str] = {}
        words = text.split()
        text_lower = text.lower()
        for lang in self.programming_languages:
            pattern = r"\b" + re.escape(lang) + r"\b"
            if re.search(pattern, text_lower):
                entities["programming_language"] = lang
                break
        for tool in self.tools:
            pattern = r"\b" + re.escape(tool) + r"\b"
            if re.search(pattern, text_lower):
                entities["tool"] = tool
                break
        for ft in self.file_types:
            pattern = r"\b\w+\." + re.escape(ft) + r"\b"
            match = re.search(pattern, text_lower)
            if match:
                entities["file_type"] = ft
                entities["file_name"] = match.group(0)
                break
        for topic, keywords in self.topic_keywords.items():
            for kw in keywords:
                if kw in text_lower:
                    entities["topic"] = topic
                    break
            if "topic" in entities:
                break
        code_pattern = r"(```[\s\S]*?```|`[^`]+`)"
        code_matches = re.findall(code_pattern, text)
        if code_matches:
            entities["has_code"] = "true"
        url_pattern = r"(https?://\S+)"
        url_matches = re.findall(url_pattern, text)
        if url_matches:
            entities["url"] = url_matches[0]
        number_pattern = r"\b(\d+)\b"
        number_matches = re.findall(number_pattern, text)
        if number_matches:
            entities["numbers"] = ",".join(number_matches[:3])
        return entities
