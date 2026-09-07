"""Genesis AI - Central orchestrator connecting all engines.
Multi-stage reasoning pipeline:
  1. UNDERSTAND  2. ANALYZE  3. PLAN  4. CHECK MEMORY
  5. KNOWLEDGE GAPS  6. RESEARCH  7. EVIDENCE  8. COMPARE
  9. CONTRADICTIONS  10. REASON  11. GENERATE  12. SELF-CRITIQUE
  13. VERIFY  14. LEARN  15. STORE EXPERIENCE
"""

import re
import time
import logging
from typing import Optional

from genesis_ai.database.db import DatabaseManager
from genesis_ai.config.settings import CONFIDENCE_THRESHOLD

from genesis_ai.core.conversation.engine import ConversationEngine
from genesis_ai.core.conversation.intent import IntentEngine
from genesis_ai.core.conversation.context import ContextEngine
from genesis_ai.core.memory.engine import MemoryEngine

from genesis_ai.knowledge.graph.engine import KnowledgeGraph
from genesis_ai.knowledge.storage.engine import KnowledgeStorage
from genesis_ai.knowledge.retrieval.engine import KnowledgeRetrieval

from genesis_ai.core.reasoning.engine import ReasoningEngine
from genesis_ai.research.search.engine import WebSearchEngine
from genesis_ai.research.extraction.engine import InformationExtraction
from genesis_ai.research.sources.engine import SourceManager
from genesis_ai.core.verification.engine import VerificationEngine
from genesis_ai.core.learning.engine import LearningEngine
from genesis_ai.skills.engine import SkillEngine
from genesis_ai.core.reflection.engine import ReflectionEngine
from genesis_ai.privacy.engine import PrivacyEngine
from genesis_ai.core.feedback.engine import FeedbackEngine
from genesis_ai.tools.engine import ToolEngine
from genesis_ai.core.curiosity.engine import CuriosityEngine
from genesis_ai.core.planning.engine import PlanningEngine

from genesis_ai.core.ai_responder import (
    classify_message_type,
    build_search_queries,
    synthesize_response,
    get_casual_response,
    _extract_name_for_creative,
)

from genesis_ai.core.understanding.engine import UnderstandingEngine, UnderstandingResult
from genesis_ai.core.analysis.engine import AnalysisEngine, AnalysisResult
from genesis_ai.core.knowledge.gaps.engine import KnowledgeGapDetector, GapAnalysisResult
from genesis_ai.core.comparison.engine import ComparisonEngine, ComparisonResult
from genesis_ai.core.contradiction.engine import ContradictionEngine, ContradictionResult
from genesis_ai.core.critic.engine import CriticEngine, CritiqueResult
from genesis_ai.core.experience.engine import ExperienceEngine, ExperienceRecord
from genesis_ai.core.code.generator import CodeGenerator
from genesis_ai.core.cognitive.engine import CognitiveEngine
from genesis_ai.core.cognitive.state import CognitiveState, Complexity, GoalType
from genesis_ai.learning.pipeline import LearningPipeline
from genesis_ai.learning.experience_memory import ExperienceMemory
from genesis_ai.core.events.engine import EventLog, Event
from genesis_ai.core.research.memory.engine import ResearchMemory

logger = logging.getLogger(__name__)


class GenesisAI:
    """
    Central orchestrator — ChatGPT/Gemini level AI assistant.

    Flow for every message:
    1. UNDERSTAND  — Classify intent, entities, complexity
    2. ANALYZE     — Decompose into components, find knowledge gaps
    3. PLAN        — Build execution plan from gaps
    4. MEMORY      — Check local knowledge cache
    5. GAPS        — Identify missing knowledge
    6. RESEARCH    — Multi-angle web search with caching
    7. EVIDENCE    — Collect and structure evidence from sources
    8. COMPARE     — Compare sources for best approach
    9. CONTRADICTIONS — Detect conflicting claims
    10. REASON     — Deep reasoning for complex queries
    11. GENERATE   — Synthesize answer from evidence
    12. SELF-CRITIQUE — Evaluate answer quality
    13. VERIFY     — Basic verification pass
    14. LEARN      — Store findings for future use
    15. EXPERIENCE — Record task outcome
    """

    def __init__(self):
        logger.info("Initializing Genesis AI...")

        self.db = DatabaseManager()
        self._ensure_response_cache_table()

        self.conversation_engine = ConversationEngine(self.db)
        self.intent_engine = IntentEngine()
        self.context_engine = ContextEngine()
        self.memory_engine = MemoryEngine(self.db)

        self.knowledge_graph = KnowledgeGraph(self.db)
        self.knowledge_storage = KnowledgeStorage(self.db)
        self.knowledge_retrieval = KnowledgeRetrieval(self.db)

        self.reasoning_engine = ReasoningEngine(self.db)
        self.web_search = WebSearchEngine()
        self.extraction = InformationExtraction()
        self.source_manager = SourceManager(self.db)
        self.verification_engine = VerificationEngine(self.db)

        self.learning_engine = LearningEngine(self.db)
        self.skill_engine = SkillEngine(self.db)
        self.reflection_engine = ReflectionEngine(self.db)
        self.privacy_engine = PrivacyEngine(self.db)
        self.feedback_engine = FeedbackEngine(self.db)
        self.tool_engine = ToolEngine(self.db)
        self.curiosity_engine = CuriosityEngine(self.db)
        self.planning_engine = PlanningEngine(self.db)

        self.understanding_engine = UnderstandingEngine(self.db)
        self.analysis_engine = AnalysisEngine(self.db)
        self.gap_detector = KnowledgeGapDetector(self.db)
        self.comparison_engine = ComparisonEngine()
        self.contradiction_engine = ContradictionEngine()
        self.critic_engine = CriticEngine(self.db)
        self.experience_engine = ExperienceEngine(self.db)
        self.event_log = EventLog(self.db)
        self.research_memory = ResearchMemory(self.db)
        self.code_generator = CodeGenerator()
        self.cognitive_engine = CognitiveEngine(self.db)
        self.learning_pipeline = LearningPipeline(self.db)
        self.experience_memory = ExperienceMemory(self.db)

        self._conversation_context: dict[str, list] = {}

        logger.info("Genesis AI initialized successfully.")

    def _ensure_response_cache_table(self):
        """Create a table for caching full Q&A responses (offline support)."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS response_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_key TEXT NOT NULL,
                query_text TEXT NOT NULL,
                response_text TEXT NOT NULL,
                msg_type TEXT DEFAULT 'FACTUAL',
                lang TEXT DEFAULT 'hinglish',
                sources TEXT DEFAULT '[]',
                created_at REAL NOT NULL,
                access_count INTEGER DEFAULT 0,
                last_accessed REAL
            )
        """)
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_response_cache_key
            ON response_cache(query_key)
        """)

    # ─── Main Chat Entry Point ─────────────────────────────────────────────────

    def chat(self, user_id: str, message: str) -> dict:
        """
        Main chat method — Cognitive pipeline.

        Builds a CognitiveState, runs it through the CognitiveEngine,
        and returns the response. The old hardcoded routing is replaced
        by dynamic decision-making.
        """
        session_id = f"{user_id}_{int(time.time())}"
        start_time = time.time()

        try:
            # Build initial cognitive state
            state = CognitiveState(
                raw_input=message,
                user_id=user_id,
                session_id=session_id,
                start_time=start_time,
            )

            # Get conversation context
            context_entity = self._get_last_entity(user_id)
            if context_entity:
                state.previous_entity = context_entity
                state.is_followup = bool(
                    re.search(r'\b(ye|yeh|woh|vo|uska|iska|that|this|it|them)\b',
                              message.lower())
                )
            state.conversation_history = self._get_context(user_id)

            # Run the full cognitive pipeline
            state = self.cognitive_engine.run_full_pipeline(state)

            # Update context for future follow-ups
            entity = self._extract_entity_from_message(message)
            self._update_context(user_id, message, state.response_text, entity)

            # ── PHASE 2: UPDATE CONTEXT MANAGER ──
            try:
                self.cognitive_engine.context_manager.update_context(
                    user_id=user_id,
                    message=message,
                    response=state.response_text or "",
                    intent=state.msg_type or "",
                    goal=state.user_goal or "unknown",
                    entities=state.entities or {},
                    topic=state.active_topic or "",
                    confidence=state.confidence_score,
                )
            except Exception:
                pass

            # Log events for backward compatibility with UI
            valid_stages = {
                "PERCEIVE": "USER_INPUT",
                "UNDERSTAND": "UNDERSTANDING_COMPLETE",
                "ASSESS_KNOWLEDGE": "MEMORY_SEARCH",
                "DECIDE": "PLAN_CREATED",
                "ACT": "SOLUTION_CREATED",
                "VERIFY": "VERIFICATION_COMPLETE",
                "LEARN": "LEARNING_COMPLETE",
            }
            for stage in state.stages_completed:
                mapped = valid_stages.get(stage)
                if mapped:
                    self.event_log.log_event(mapped, {}, session_id)
            self.event_log.log_event(
                "ANSWER_READY",
                {"total_duration": state.total_duration},
                session_id,
            )

            return {
                "response_text": state.response_text,
                "intent": state.msg_type,
                "confidence": state.confidence_score,
                "sources_used": state.sources_used,
                "knowledge_stored": state.knowledge_updated,
                "skills_created": bool(state.skills_created),
                "processing_time_ms": int(state.total_duration * 1000),
                "user_id": user_id,
                "pipeline_stages": self.event_log.get_stage_timings(session_id),
                # Phase 2: context fields
                "active_topic": state.active_topic or "",
                "user_goal": state.user_goal or "",
                "topic_changed": state.topic_changed,
                "resolved_references": state.resolved_references or {},
                "context_relevance": round(state.context_relevance_score, 2),
            }

        except Exception as e:
            logger.error("Error in chat: %s", e, exc_info=True)
            err_lang = self.conversation_engine._detect_language(message)
            error_msgs = {
                'hindi': "माफ़ कीजिए, एक error आई। कृपया दोबारा try करें।",
                'hinglish': "Sorry yaar, kuch gadbad ho gayi. Dobara try karo!",
                'english': "I encountered an error. Please try again.",
            }
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "response_text": error_msgs.get(err_lang, error_msgs["english"]),
                "intent": "ERROR",
                "confidence": 0.0,
                "sources_used": [],
                "knowledge_stored": False,
                "skills_created": False,
                "processing_time_ms": elapsed_ms,
                "user_id": user_id,
                "pipeline_stages": {},
            }

    def _resolve_followup(self, message: str, context_entity: str) -> str:
        """Resolve follow-up references using structural patterns, not exact word lists."""
        msg = message.lower().strip()
        # Detect if message contains pronoun-like references (structural: short + starts with/contains reference)
        pronoun_pattern = re.compile(
            r'\b(ye|yeh|woh|vo|voh|uska|iska|uske|iske|uski|iski|unka|'
            r'usko|isko|unhe|inhe|isme|usme|ismein|'
            r'this|that|it|he|she|they|him|her|them|its|the)\b',
            re.IGNORECASE,
        )
        words = msg.split()
        has_pronoun = any(pronoun_pattern.search(w) for w in words)
        if not has_pronoun:
            return message
        # Replace pronouns with context entity
        resolved = pronoun_pattern.sub(context_entity, msg)
        return resolved.strip()

    def _generate_answer(self, understanding, evidence, comparison, local_knowledge, lang):
        """Generate a comprehensive answer from all gathered evidence."""
        msg_lower = understanding.raw_message.lower()

        def L(hi, mix, en):
            return {'hindi': hi, 'hinglish': mix, 'english': en}.get(lang, mix)

        # If we have comparison with best approach, prefer that
        if comparison and comparison.best_approach and comparison.approaches:
            best = comparison.approaches[0]
            parts = []
            parts.append(f"**{understanding.raw_message.strip().title()}**\n")
            parts.append(L(
                f"**Best approach: {comparison.best_approach}**\n\n",
                f"**Best approach: {comparison.best_approach}**\n\n",
                f"**Best approach: {comparison.best_approach}**\n\n",
            ))

            # Synthesize from best approach evidence
            source_evidence = [e for e in evidence if e.get("topic", "") in comparison.best_approach or True]
            if source_evidence:
                merged = self._merge_evidence_text(source_evidence, 600)
                parts.append(self._make_flowing_paragraph(merged))

            # Add tradeoffs if available
            if comparison.tradeoffs:
                parts.append(f"\n\n**{L('Tradeoffs:', 'Tradeoffs:', 'Tradeoffs:')}**")
                for t_item in comparison.tradeoffs[:3]:
                    pros_str = ", ".join(t_item.get("pros", [])[:3])
                    cons_str = ", ".join(t_item.get("cons", [])[:3])
                    parts.append(f"- {t_item.get('approach', '')}: {L('Pros', 'Pros', 'Pros')}: {pros_str} | {L('Cons', 'Cons', 'Cons')}: {cons_str}")

            parts.append(f"\n\n**{L('Confidence:', 'Confidence:', 'Confidence:')}** {comparison.confidence:.0%}")

            # Add sources
            unique_sources = list(dict.fromkeys(e.get("source", "") for e in evidence if e.get("source")))
            if unique_sources:
                parts.append(f"\n\n**{L('Sources:', 'Sources:', 'Sources:')}**")
                for src in unique_sources[:5]:
                    parts.append(f"- {src}")

            return "\n".join(parts)

        # Standard evidence synthesis
        if evidence:
            merged = self._merge_evidence_text(evidence, 700)
            topic = understanding.raw_message.strip().title()

            body = self._make_flowing_paragraph(merged)
            result = f"**{topic}**\n\n{body}"

            # Add key points from extra evidence
            extra = self._get_extra_evidence_points(evidence[1:], merged, 3)
            if extra:
                result += f"\n\n**{L('Key points:', 'Key points:', 'Key points:')}**"
                for p in extra:
                    result += f"\n- {p}"

            # Add sources
            unique_sources = list(dict.fromkeys(e.get("source", "") for e in evidence if e.get("source")))
            if unique_sources:
                result += f"\n\n**{L('Sources:', 'Sources:', 'Sources:')}**"
                for src in unique_sources[:5]:
                    result += f"\n- {src}"

            return result

        # Fallback to old synthesis
        return self._generate_fallback_response(understanding.raw_message, lang)

    def _merge_evidence_text(self, evidence, max_chars=800):
        """Merge multiple evidence items into coherent text."""
        seen = set()
        parts = []
        total = 0
        for item in evidence:
            text = item.get("claim", "")
            if not text:
                continue
            sentences = re.split(r'(?<=[.!?])\s+', text)
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

    def _make_flowing_paragraph(self, text):
        """Convert merged text into a clean, readable paragraph."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        good = [s.strip() for s in sentences if len(s.strip()) > 20]
        return ' '.join(good[:5]) if good else text[:400]

    def _get_extra_evidence_points(self, evidence, main_text, count):
        """Get additional bullet points from extra evidence."""
        extra = []
        main_lower = main_text.lower()
        for item in evidence:
            text = item.get("claim", "")[:200].rsplit(' ', 1)[0]
            if text and text.lower()[:40] not in main_lower and len(text) > 20:
                extra.append(text)
            if len(extra) >= count:
                break
        return extra

    # ─── Handler: Factual Questions ──────────────────────────────────────────

    def _handle_factual(self, user_id: str, message: str, lang: str) -> tuple:
        """Handle factual questions — search internet, synthesize, cache."""
        sources_used = []
        knowledge_stored = False

        corrected = self._fix_typos(message)

        cached = self._check_cache(corrected)
        if cached:
            logger.info("Cache hit for: %s", corrected)
            return cached, [], False

        queries = build_search_queries(corrected, 'FACTUAL')

        all_results = self._multi_search(queries, max_results=6)

        if not all_results:
            return self._no_results_response(message, lang), sources_used, knowledge_stored

        for r in all_results:
            self.source_manager.track_source(r.url, r.title)
            if r.source_name:
                sources_used.append(r.source_name)

        response = synthesize_response(corrected, all_results, lang, 'FACTUAL')

        if not response:
            return self._no_results_response(message, lang), sources_used, knowledge_stored

        self._store_cache(corrected, response, 'FACTUAL', lang, sources_used)

        try:
            snippets_text = " ".join(r.snippet for r in all_results if r.snippet)
            facts = self.extraction.extract_facts(snippets_text[:2000])
            if facts:
                self.learning_engine.learn_from_research({
                    "findings": [{"claim": f.claim, "confidence": f.confidence, "source": "web"}
                                 for f in facts[:5]],
                    "sources": [{"name": r.source_name, "url": r.url} for r in all_results[:3]],
                    "confidence": 0.7,
                })
                knowledge_stored = True
        except Exception as e:
            logger.warning("Knowledge storage failed: %s", e)

        return response, sources_used, knowledge_stored

    # ─── Handler: Creative Content ────────────────────────────────────────────

    def _handle_creative(self, user_id: str, message: str, lang: str) -> tuple:
        """Handle creative requests (shayari, jokes, stories, etc.)"""
        sources_used = []
        knowledge_stored = False

        cached = self._check_cache(message)
        if cached:
            logger.info("Creative cache hit for: %s", message)
            return cached, [], False

        name_for_creative = _extract_name_for_creative(message)

        queries = build_search_queries(message, 'CREATIVE', name_for_creative)

        all_results = self._multi_search(queries, max_results=8)

        if not all_results:
            return self._creative_fallback(message, lang), sources_used, knowledge_stored

        for r in all_results:
            if r.url:
                self.source_manager.track_source(r.url, r.title)
            if r.source_name:
                sources_used.append(r.source_name)

        response = synthesize_response(
            message, all_results, lang, 'CREATIVE',
            name_for_creative=name_for_creative
        )

        if not response:
            return self._creative_fallback(message, lang), sources_used, knowledge_stored

        self._store_cache(message, response, 'CREATIVE', lang, sources_used)
        knowledge_stored = True

        return response, sources_used, knowledge_stored

    # ─── Handler: Follow-up Questions ────────────────────────────────────────

    def _handle_followup(self, user_id: str, message: str, lang: str, context_entity: str) -> tuple:
        """Handle follow-up questions that reference previous context."""
        if not context_entity:
            return self._handle_factual(user_id, message, lang)

        queries = build_search_queries(message, 'FOLLOWUP', context_entity)

        all_results = self._multi_search(queries, max_results=6)

        if not all_results:
            return self._handle_factual(user_id, message, lang)

        sources_used = [r.source_name for r in all_results if r.source_name]

        followup_query = f"{context_entity} {message}"
        response = synthesize_response(followup_query, all_results, lang, 'FOLLOWUP', context_entity)

        if not response:
            return self._handle_factual(user_id, message, lang)

        self._store_cache(followup_query, response, 'FOLLOWUP', lang, sources_used)

        return response, sources_used, True

    # ─── Handler: Code Generation ────────────────────────────────────────────

    def _handle_code(self, user_id: str, message: str, lang: str) -> tuple:
        """Handle coding requests — local generation first, web search as fallback."""
        sources_used = []
        knowledge_stored = False

        cached = self._check_cache(message)
        if cached:
            return cached, [], False

        # Try local code generation first
        code_response = self._generate_code(message, lang)

        if code_response:
            self._store_cache(message, code_response, 'CODE', lang, sources_used)
            return code_response, sources_used, knowledge_stored

        # Fallback: web search for reference code
        queries = [
            f"{message} code example",
            f"{message} implementation tutorial",
        ]
        all_results = self._multi_search(queries, max_results=5)

        if all_results:
            sources_used = [r.source_name for r in all_results if r.source_name]
            code_response = self._synthesize_code_from_web(message, all_results, lang)
            self._store_cache(message, code_response, 'CODE', lang, sources_used)
            return code_response, sources_used, True

        return self._code_fallback(message, lang), sources_used, knowledge_stored

    def _generate_code(self, message: str, lang: str) -> Optional[str]:
        """Delegate to CodeGenerator for local code generation."""
        return self.code_generator.generate(message)

    def _synthesize_code_from_web(self, message: str, results: list, lang: str) -> str:
        """Synthesize code response using web search results."""
        code_found = ""
        explanation = ""
        topic = re.sub(r'\b(banao|bana|create|write|build|generate|code|program)\b', '', message, flags=re.IGNORECASE).strip().title()

        for r in results:
            if not r.snippet:
                continue
            snippet = r.snippet
            if re.search(r'(def |import |class |function |const |var |let |\{|\})', snippet):
                code_found = snippet[:500]
                break

        if not code_found:
            explanation = " ".join(r.snippet for r in results[:2] if r.snippet)[:600]
        
        L = lambda hi, mix, en: {'hindi': hi, 'hinglish': mix, 'english': en}.get(lang, mix)

        if code_found:
            return (
                f"{L(f'{topic} के लिए code:', f'{topic} ka code:', f'Here is the code for {topic}:')}"
                f"\n\n```\n{code_found}\n```"
                f"\n\n{L('क्या इसमें changes चाहिए?', 'Kuch changes chahiye?', 'Need any modifications?')} 😊"
            )
        else:
            return (
                f"**{topic}**\n\n"
                f"{explanation}\n\n"
                f"{L('Kya aap aur specific batayenge? Jaise language, features, etc.', 'Kya aur specific batayenge?', 'Could you be more specific about the requirements?')} 😊"
            )

    def _code_fallback(self, message: str, lang: str) -> str:
        """When no code template available — provide a helpful response."""
        topic = re.sub(r'\b(banao|bana|create|write|build|generate|code|program)\b', '', message, flags=re.IGNORECASE).strip().title()
        return {
            'hindi': f"'{topic}' के लिए code बनाने के लिए, कृपया बताइए:\n\n- किस programming language में? (Python, JavaScript, etc.)\n- क्या functionality चाहिए?\n\nजितना बताएंगे, उतना better code बनेगा!",
            'hinglish': f"'{topic}' ka code banane ke liye batao:\n\n- Kaunsi language? (Python, JS, etc.)\n- Kya functionality chahiye?\n\nBatao, code bana dunga!",
            'english': f"I can help you build '{topic}'. Please tell me:\n\n- Which programming language? (Python, JavaScript, etc.)\n- What specific functionality do you need?\n\nThe more details you give, the better the code!",
        }.get(lang, f"Please tell me more about '{topic}' so I can write the code!")

    # ─── Identity & Special Responses ────────────────────────────────────────

    def _is_identity_question(self, message: str) -> bool:
        """Detect identity questions using structural patterns, not exact strings."""
        msg = message.lower().strip()
        self_references = ['genesis', 'yourself', 'tum', 'aap', 'tera', 'tumhara', 'apna', 'your', 'you']
        identity_q_words = ['who', 'what', 'kaun', 'kya', 'name', 'naam']
        has_self_ref = any(w in msg for w in self_references)
        has_identity_q = any(w in msg for w in identity_q_words)
        has_about_self = bool(re.search(r'\b(tell|batao|samjhao)\b.{0,20}\b(yourself|apne\s+aap|tum\s+khud)\b', msg))
        return (has_self_ref and has_identity_q) or has_about_self

    def _identity_response(self, lang: str) -> str:
        """Generate identity response dynamically based on current capabilities."""
        def L(hi, mix, en):
            return {'hindi': hi, 'hinglish': mix, 'english': en}.get(lang, mix)
        capabilities = []
        if hasattr(self, 'web_search'):
            capabilities.append(L(
                "🔍 **Research** — किसी भी topic पर internet से जानकारी लाना",
                "🔍 **Research** — Kisi bhi topic pe internet se info lana",
                "🔍 **Research** — Find information on any topic from the internet",
            ))
        capabilities.append(L(
            "💻 **Coding** — Programs, apps, APIs बनाना",
            "💻 **Coding** — Programs, apps, APIs banana",
            "💻 **Coding** — Build programs, apps, APIs",
        ))
        capabilities.append(L(
            "💬 **Conversation** — हर topic पर बात करना",
            "💬 **Baat** — Har topic pe conversation",
            "💬 **Conversation** — Chat about anything",
        ))
        cap_text = "\n".join(f"- {c}" for c in capabilities)
        return L(
            f"मैं **Genesis AI** हूँ — आपका personal AI assistant! 😊\n\n{cap_text}\n\nपूछिए जो चाहिए! 🚀",
            f"Main **Genesis AI** hoon — tumhara personal AI assistant! 😊\n\n{cap_text}\n\nBatao kya karna hai! 🚀",
            f"I'm **Genesis AI** — your personal AI assistant! 😊\n\n{cap_text}\n\nAsk me anything! 🚀",
        )

    # ─── Context Management ───────────────────────────────────────────────────

    def _get_context(self, user_id: str) -> list:
        """Get recent conversation history for a user."""
        return self._conversation_context.get(user_id, [])

    def _get_last_entity(self, user_id: str) -> Optional[str]:
        """Get the last discussed entity from conversation history."""
        history = self._conversation_context.get(user_id, [])
        for turn in reversed(history):
            entity = turn.get('entity')
            if entity:
                return entity
        return None

    def _update_context(self, user_id: str, message: str, response: str, entity: Optional[str]):
        """Update conversation context for a user."""
        if user_id not in self._conversation_context:
            self._conversation_context[user_id] = []
        history = self._conversation_context[user_id]
        history.append({
            'role': 'user',
            'content': message,
            'entity': entity,
            'timestamp': time.time(),
        })
        history.append({
            'role': 'assistant',
            'content': response[:300],
            'timestamp': time.time(),
        })
        if len(history) > 20:
            self._conversation_context[user_id] = history[-20:]

    def _extract_entity_from_message(self, message: str) -> Optional[str]:
        """Extract the main entity/topic being discussed."""
        msg_lower = message.lower()
        patterns = [
            r'\b(?:who is|kaun hai|kon hai|about|ke baare|who was)\s+(.+?)(?:\?|$)',
            r'\b(?:what is|kya hai)\s+(.+?)(?:\?|$)',
            r'^(.+?)\s+(?:ke baare|about|kya hai|kaun hai)',
        ]
        for p in patterns:
            m = re.search(p, msg_lower)
            if m:
                entity = m.group(1).strip()
                entity = re.sub(r'\b(aur|bhi|kya|hai|the|a|an)\b', '', entity).strip()
                if 2 < len(entity) < 50:
                    return entity.title()
        proper = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', message)
        if proper:
            return proper[0]
        return None

    # ─── Cache System (Offline Support) ──────────────────────────────────────

    def _make_cache_key(self, query: str) -> str:
        """Create a normalized cache key from query."""
        key = query.lower().strip()
        key = re.sub(r'\b(kya|hai|kaun|kaise|kab|aur|bhi|to|mein|ka|ki|ke|ko|se|pe|par)\b', '', key)
        key = re.sub(r'\s+', ' ', key).strip()
        key = re.sub(r'[?!.,;]+', '', key)
        return key[:200]

    def _check_cache(self, query: str) -> Optional[str]:
        """Check if a response is cached (offline support)."""
        key = self._make_cache_key(query)
        try:
            row = self.db.fetch_one(
                "SELECT response_text, id FROM response_cache WHERE query_key = ? ORDER BY created_at DESC LIMIT 1",
                (key,)
            )
            if row:
                self.db.execute(
                    "UPDATE response_cache SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                    (time.time(), row[1])
                )
                return row[0]
        except Exception as e:
            logger.warning("Cache check failed: %s", e)
        return None

    def _store_cache(self, query: str, response: str, msg_type: str, lang: str, sources: list):
        """Store response in cache for offline use."""
        key = self._make_cache_key(query)
        try:
            existing = self.db.fetch_one(
                "SELECT id FROM response_cache WHERE query_key = ?", (key,)
            )
            if not existing:
                import json
                self.db.execute(
                    """INSERT INTO response_cache
                       (query_key, query_text, response_text, msg_type, lang, sources, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (key, query[:500], response, msg_type, lang,
                     json.dumps(sources[:5]), time.time())
                )
                logger.info("Cached response for: %s", query[:50])
        except Exception as e:
            logger.warning("Cache store failed: %s", e)

    # ─── Multi-Search ─────────────────────────────────────────────────────────

    def _multi_search(self, queries: list, max_results: int = 6) -> list:
        """Try multiple search queries and return deduplicated results."""
        all_results = []
        seen_urls = set()

        for q in queries:
            try:
                results = self.web_search.search(q, max_results=max_results)
                for r in results:
                    if r.url and r.url not in seen_urls and r.snippet and len(r.snippet) > 40:
                        seen_urls.add(r.url)
                        all_results.append(r)
                if len(all_results) >= max_results:
                    break
            except Exception as e:
                logger.error("Search error for '%s': %s", q, e)

        return all_results[:max_results + 2]

    # ─── Fallback Responses ──────────────────────────────────────────────────

    def _no_results_response(self, message: str, lang: str) -> str:
        return {
            'hindi': f"माफ़ कीजिए, '{message}' के बारे में अभी internet से जानकारी नहीं मिल पाई। क्या आप सवाल थोड़ा अलग तरह से पूछ सकते हैं? 😊",
            'hinglish': f"Sorry yaar, '{message}' ke baare mein abhi internet se info nahi mili. Kya thoda alag pooch sakte ho? 😊",
            'english': f"I couldn't find information about '{message}' right now. Could you rephrase or try a different query? 😊",
        }.get(lang, f"Couldn't find results for '{message}'. Please try rephrasing. 😊")

    def _creative_fallback(self, message: str, lang: str) -> str:
        return {
            'hindi': "माफ़ कीजिए, अभी internet से content नहीं मिल पाया। Internet connection check करें और फिर try करें। 😊",
            'hinglish': "Sorry yaar, internet se content nahi mila abhi. Connection check karo aur phir try karo! 😊",
            'english': "Sorry, couldn't fetch content from the internet right now. Please check your connection and try again! 😊",
        }.get(lang, "Couldn't fetch content. Please check internet and try again. 😊")

    def _generate_fallback_response(self, message: str, lang: str) -> str:
        """Generate a fallback response when no evidence is available."""
        return {
            'hindi': f"माफ़ कीजिए, '{message}' के बारे में अभी पर्याप्त जानकारी नहीं मिल पाई। कृपया दोबारा try करें। 😊",
            'hinglish': f"Sorry yaar, '{message}' ke baare mein abhi info nahi mili. Dobara try karo! 😊",
            'english': f"I couldn't gather enough information about '{message}' right now. Please try again. 😊",
        }.get(lang, f"Couldn't find enough information about '{message}'. Please try again. 😊")

    # ─── Typo Fixer ──────────────────────────────────────────────────────────

    def _fix_typos(self, text: str) -> str:
        """Fix common typos before searching."""
        typos = {
            r'\blikedlist\b': 'linked list',
            r'\blink\s*list\b': 'linked list',
            r'\blinkedlist\b': 'linked list',
            r'\bwhat\s+iis\b': 'what is',
            r'\bwhat\s+iiis\b': 'what is',
            r'\bwhatt\s+is\b': 'what is',
            r'\bhow\s+iiis\b': 'how is',
            r'\biis\b': 'is',
            r'\bpaiidda\b': 'paida',
            r'\bpaaida\b': 'paida',
            r'\bpaida\b': 'born',
            r'\bkidhar\b': 'kahan',
            r'\bkb\b': 'kab',
            r'\bwho\s+i\s+(\w+)\b': r'who is \1',
        }
        result = text
        for pattern, replacement in typos.items():
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result

    # ─── Legacy Compatibility Methods ────────────────────────────────────────

    def research(self, query: str) -> dict:
        web_results = self.web_search.search(query, max_results=5)
        sources_used = []
        findings = []
        for r in web_results:
            source_id = self.source_manager.track_source(r.url, r.title)
            sources_used.append({"name": r.source_name, "url": r.url, "reliability": 0.5})
            if r.snippet:
                facts = self.extraction.extract_facts(r.snippet)
                for f in facts:
                    findings.append({"claim": f.claim, "confidence": f.confidence, "source": r.source_name})
        source_dicts = [{"source_name": s["name"], "url": s["url"], "snippet": "", "reliability": s["reliability"]} for s in sources_used]
        verification = self.verification_engine.verify_claim(query, source_dicts)
        learn_result = self.learning_engine.learn_from_research({
            "findings": findings[:5], "sources": sources_used, "confidence": verification.confidence,
        })
        research_session_id = self.db.insert_research_session(user_id=1, query=query)
        self.db.update_research_session(
            research_session_id, sources_checked=len(sources_used),
            findings=[f["claim"] for f in findings[:5]], confidence=verification.confidence, status="completed",
        )
        return {
            "query": query, "sources_found": len(sources_used), "sources_used": sources_used,
            "findings": findings[:5],
            "verification": {"confidence": verification.confidence, "status": verification.status, "evidence_count": verification.evidence_count},
            "knowledge_stored": learn_result.success, "research_session_id": research_session_id,
        }

    def get_memory_stats(self) -> dict:
        return self.memory_engine.get_memory_stats()

    def get_knowledge_stats(self) -> dict:
        concepts = self.db.list_concepts()
        all_knowledge = []
        for c in concepts:
            items = self.db.get_knowledge_for_concept(c["id"])
            all_knowledge.extend(items)
        verified = sum(1 for k in all_knowledge if k.get("verification_status") == "verified")
        disputed = sum(1 for k in all_knowledge if k.get("verification_status") == "disputed")
        relationships = len(self.db.traverse_knowledge_graph(concepts[0]["id"], max_depth=1)) if concepts else 0
        return {
            "total_concepts": len(concepts), "total_knowledge": len(all_knowledge),
            "verified_knowledge": verified, "disputed_knowledge": disputed,
            "total_relationships": relationships,
        }

    def get_learning_stats(self) -> dict:
        return self.learning_engine.get_learning_stats()

    def get_skill_stats(self) -> dict:
        return self.skill_engine.get_skill_stats()

    def get_status(self) -> dict:
        memory_stats = self.memory_engine.get_memory_stats()
        knowledge_stats = self.get_knowledge_stats()
        skill_stats = self.skill_engine.get_skill_stats()
        online = self.web_search.is_online()
        return {
            "status": "online" if online else "offline",
            "memory_count": memory_stats.get("total_memories", 0),
            "knowledge_count": knowledge_stats.get("total_knowledge", 0),
            "concept_count": knowledge_stats.get("total_concepts", 0),
            "skill_count": skill_stats.get("total_skills", 0),
            "curiosity_queue": self.curiosity_engine.get_queue_status(),
        }

    def process_feedback(self, feedback: dict) -> dict:
        user_id = feedback.get("user_id", 1)
        conversation_id = feedback.get("conversation_id", 0)
        feedback_type = feedback.get("type", "positive")
        details = feedback.get("details", {})
        result = self.feedback_engine.process_feedback(
            user_id=user_id, conversation_id=conversation_id,
            feedback_type=feedback_type, details=details,
        )
        return {
            "success": result.success, "feedback_type": result.feedback_type,
            "message": result.message, "confidence_adjustment": result.confidence_adjustment,
        }

    def reflect(self) -> dict:
        recent_memories = self.memory_engine.get_recent_memories(10)
        gaps = self.reflection_engine.identify_knowledge_gaps()
        curiosity_status = self.curiosity_engine.get_queue_status()
        return {
            "what_learned": [m["content"][:100] for m in recent_memories[:5]],
            "knowledge_gaps": gaps[:5], "curiosity_status": curiosity_status,
            "improvements": self._suggest_improvements(),
        }

    def _suggest_improvements(self) -> list:
        improvements = []
        stats = self.get_learning_stats()
        if stats.get("verified_knowledge", 0) < stats.get("knowledge_claims", 1) * 0.5:
            improvements.append("More knowledge verification needed")
        memory_stats = self.memory_engine.get_memory_stats()
        if memory_stats.get("total_memories", 0) > 500:
            improvements.append("Consider memory pruning for better performance")
        skill_stats = self.skill_engine.get_skill_stats()
        if skill_stats.get("total_skills", 0) == 0:
            improvements.append("No skills created yet — start a task to build procedural knowledge")
        return improvements

    def export_data(self, user_id: str) -> dict:
        return self.privacy_engine.export_user_data(user_id)

    def get_privacy_report(self) -> dict:
        return self.privacy_engine.get_privacy_report()

    def get_learning_timeline(self) -> list:
        sessions = self.db.list_learning_sessions(user_id=1, limit=20)
        return [{
            "id": s["id"], "topic": s["topic"],
            "type": s.get("session_type", "general"),
            "status": s.get("status", "active"),
            "started_at": s.get("started_at"),
        } for s in sessions]
