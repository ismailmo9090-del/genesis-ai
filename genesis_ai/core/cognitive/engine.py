"""CognitiveEngine — central cognitive orchestrator.

Replaces the hardcoded if/elif routing in main.py with a dynamic
cognitive pipeline. This is the "brain" that coordinates all other engines.

Flow:
  INPUT → PERCEIVE → UNDERSTAND → DECIDE → ACT → VERIFY → RESPOND → LEARN

Each step reads from and writes to the CognitiveState. The state is
NEVER exposed to the user — only the final response is.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Optional

from .state import (
    CognitiveState,
    Complexity,
    DecisionAction,
    GoalType,
    KnowledgeStatus,
)
from .decision import DecisionOrchestrator

if TYPE_CHECKING:
    from genesis_ai.database.db import DatabaseManager

logger = logging.getLogger(__name__)


class CognitiveEngine:
    """Central cognitive orchestrator.

    This engine does NOT generate text. It:
    1. Builds a CognitiveState from the input
    2. Decides what action to take
    3. Coordinates other engines to execute that action
    4. Verifies the result
    5. Triggers learning

    It replaces the hardcoded routing in main.py with dynamic decisions.
    """

    def __init__(self, db: "DatabaseManager"):
        self.db = db
        self.decision_orchestrator = DecisionOrchestrator()
        self._ensure_cognitive_state_table()

    def _ensure_cognitive_state_table(self):
        """Store cognitive states for debugging and learning."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS cognitive_states (
                session_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                duration REAL DEFAULT 0.0
            )
        """)

    def perceive(self, state: CognitiveState) -> CognitiveState:
        """Stage 1: PERCEIVE — extract raw signals from input.

        This is the lightest stage. No reasoning, just signal extraction.
        """
        msg = state.raw_input.strip()
        state.cleaned_input = msg
        state.word_count = len(msg.split())
        state.detected_language = self._detect_language(msg)

        # Structural signal detection (NOT content-based)
        state.is_question = "?" in msg or any(
            w in msg.lower()
            for w in ["who", "what", "when", "where", "why", "how",
                       "kaun", "kya", "kab", "kahan", "kyun", "kaise"]
        )
        state.is_command = any(
            w in msg.lower()
            for w in ["make", "create", "write", "build", "generate",
                       "banao", "bana", "likho", "fix", "debug"]
        )
        state.is_greeting = state.word_count <= 5 and any(
            w in msg.lower()
            for w in ["hi", "hello", "hey", "namaste", "bye",
                       "kya haal", "kaise ho", "sup", "yo"]
        )
        state.contains_code = any(
            w in msg.lower()
            for w in ["code", "program", "function", "class", "api",
                       "python", "javascript", "java", "html", "css"]
        )
        state.contains_entities = bool(
            __import__("re").search(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", msg)
        )

        state.mark_stage("PERCEIVE")
        return state

    def understand(self, state: CognitiveState) -> CognitiveState:
        """Stage 2: UNDERSTAND — classify intent, extract entities, assess complexity.

        Uses UnderstandingEngine for intent/entity extraction, then
        enriches the CognitiveState with the results.
        """
        # Import here to avoid circular dependency
        from genesis_ai.core.understanding.engine import UnderstandingEngine
        engine = UnderstandingEngine(self.db)
        understanding = engine.understand(state.cleaned_input)

        # Map understanding to cognitive state
        state.intent = understanding.intent
        state.domain = understanding.domain
        state.entities = understanding.entities
        state.constraints = understanding.constraints
        state.output_type = understanding.output_type
        state.sub_goals = understanding.sub_tasks

        # Map task_type to GoalType
        task_goal_map = {
            "conversation": GoalType.CONVERSATION,
            "factual": GoalType.FACTUAL,
            "code": GoalType.CODE,
            "creative": GoalType.CREATIVE,
            "analysis": GoalType.RESEARCH,
            "math": GoalType.FACTUAL,
        }
        state.goal_type = task_goal_map.get(understanding.task_type, GoalType.UNKNOWN)

        # Map complexity
        complexity_map = {
            "simple": Complexity.SIMPLE,
            "moderate": Complexity.MODERATE,
            "complex": Complexity.COMPLEX,
        }
        state.complexity = complexity_map.get(understanding.complexity, Complexity.SIMPLE)

        # Override: greetings are always trivial
        if state.is_greeting or state.goal_type == GoalType.CONVERSATION:
            state.complexity = Complexity.TRIVIAL
            state.goal_type = GoalType.CONVERSATION

        # Override: identity questions
        if self._is_identity_question(state.raw_input):
            state.goal_type = GoalType.IDENTITY
            state.complexity = Complexity.TRIVIAL

        state.mark_stage("UNDERSTAND")
        return state

    def assess_knowledge(self, state: CognitiveState) -> CognitiveState:
        """Stage 3: ASSESS_KNOWLEDGE — determine what is known vs unknown.

        Checks local memory, knowledge base, and experience to determine
        the knowledge status for this specific query.
        """
        # Check local knowledge
        from genesis_ai.knowledge.retrieval.engine import KnowledgeRetrieval
        retrieval = KnowledgeRetrieval(self.db)
        state.local_knowledge = retrieval.retrieve(
            state.cleaned_input,
            {"topic": state.domain},
        ) or []

        # Check memory for relevant past interactions
        from genesis_ai.core.memory.engine import MemoryEngine
        memory = MemoryEngine(self.db)
        state.relevant_memories = memory.search_memories(
            state.cleaned_input, limit=5
        )

        # Check experience for similar past tasks
        from genesis_ai.core.experience.engine import ExperienceEngine
        exp_engine = ExperienceEngine(self.db)
        state.relevant_experiences = exp_engine.find_similar_experiences(
            state.cleaned_input, limit=5
        )

        # Determine knowledge status
        if state.local_knowledge:
            state.knowledge_status = KnowledgeStatus.KNOWN
        elif state.relevant_memories:
            state.knowledge_status = KnowledgeStatus.KNOWN
        elif state.relevant_experiences:
            state.knowledge_status = KnowledgeStatus.KNOWN
        else:
            state.knowledge_status = KnowledgeStatus.UNKNOWN

        # Check if knowledge might be outdated
        if state.knowledge_status == KnowledgeStatus.KNOWN:
            # If oldest knowledge is > 24h old and topic is time-sensitive
            # (structural check, not content-specific)
            if self._is_time_sensitive(state):
                state.knowledge_status = KnowledgeStatus.OUTDATED

        state.mark_stage("ASSESS_KNOWLEDGE")
        return state

    def decide(self, state: CognitiveState) -> CognitiveState:
        """Stage 4: DECIDE — choose the best action.

        Delegates to DecisionOrchestrator for dynamic decision-making.
        """
        state = self.decision_orchestrator.decide(state)
        state.mark_stage("DECIDE")
        return state

    def act(self, state: CognitiveState) -> CognitiveState:
        """Stage 5: ACT — execute the decided action.

        Routes to the appropriate handler based on the decision,
        NOT based on hardcoded question patterns.
        """
        action = state.selected_action

        if action == DecisionAction.RESPOND:
            state = self._act_respond(state)
        elif action == DecisionAction.RECALL:
            state = self._act_recall(state)
        elif action == DecisionAction.SEARCH:
            state = self._act_search(state)
        elif action == DecisionAction.DEEP_RESEARCH:
            state = self._act_deep_research(state)
        elif action == DecisionAction.REASON:
            state = self._act_reason(state)
        elif action == DecisionAction.ASK_CLARIFICATION:
            state = self._act_clarify(state)
        elif action == DecisionAction.USE_TOOL:
            state = self._act_tool(state)
        else:
            state = self._act_respond(state)

        state.mark_stage("ACT")
        return state

    def verify(self, state: CognitiveState) -> CognitiveState:
        """Stage 6: VERIFY — check if response is good enough.

        Uses CriticEngine to evaluate the response quality.
        If issues found, triggers revision.
        """
        if not state.response_text:
            state.needs_revision = True
            state.evaluation_issues.append("No response generated")
            return state

        # Evaluate response quality
        from genesis_ai.core.critic.engine import CriticEngine
        critic = CriticEngine(self.db)

        # Build research context for critic
        research_ctx = [
            {"text": e.get("claim", ""), "source_name": e.get("source", ""),
             "url": e.get("url", "")}
            for e in state.evidence[:5]
        ]

        critique = critic.critique(
            answer=state.response_text,
            question=state.raw_input,
            research=research_ctx,
            understanding={
                "intent": state.intent,
                "requirements": state.constraints,
            },
        )

        state.response_confidence = critique.score / 10.0  # normalize to 0-1

        # Check for issues
        if critique.score < 50:
            state.needs_revision = True
            state.evaluation_issues.extend(
                [str(issue) for issue in critique.issues[:3]]
            )

        # Check for copied research text
        if self._has_raw_research_text(state):
            state.needs_revision = True
            state.evaluation_issues.append("Response contains raw research text")

        state.mark_stage("VERIFY")
        return state

    def learn(self, state: CognitiveState) -> CognitiveState:
        """Stage 7: LEARN — extract experience and update knowledge.

        Records the task outcome, extracts lessons, and triggers
        generalization for future reuse.
        """
        if state.complexity == Complexity.TRIVIAL:
            # Don't learn from trivial interactions
            state.mark_stage("LEARN")
            return state

        # Build experience for learning pipeline
        from genesis_ai.learning.experience_memory import Experience
        from genesis_ai.learning.pipeline import LearningPipeline

        result = "success" if not state.needs_revision else "partial"
        if state.error:
            result = "failure"

        experience = Experience(
            task=state.raw_input[:200],
            goal=state.intent,
            context={
                "goal_type": state.goal_type.value,
                "complexity": state.complexity.value,
                "domain": state.domain,
                "entities": state.entities,
            },
            observations=state.stages_completed,
            actions=[state.selected_action.value],
            tools_used=[],
            errors=[state.error] if state.error else [],
            attempts=[],
            result={"response": state.response_text[:200], "outcome": result},
            success=not state.needs_revision and not state.error,
            evidence=state.evidence[:5],
            reflection=state.raw_input[:100],
            metadata={"user_id": state.user_id, "session_id": state.session_id},
        )

        # Process through learning pipeline
        pipeline = LearningPipeline(self.db)
        learning_result = pipeline.process_experience(experience)

        # Also record in legacy experience engine for backward compatibility
        from genesis_ai.core.experience.engine import ExperienceEngine, ExperienceRecord
        exp_engine = ExperienceEngine(self.db)
        legacy_exp = ExperienceRecord(
            task_id=state.session_id,
            task_description=state.raw_input[:200],
            approach=state.selected_action.value,
            knowledge_used=[m.get("content", "")[:100] for m in state.relevant_memories[:3]],
            research_used=state.sources_used,
            errors=[state.error] if state.error else [],
            solution_summary=state.response_text[:200],
            result=result,
            lessons=learning_result.lessons_learned,
            duration=time.time() - state.start_time,
        )
        exp_engine.create_experience(legacy_exp)

        state.experience_recorded = True
        state.lessons_learned = learning_result.lessons_learned
        state.generalizations = learning_result.generalizations
        state.skills_created = [s.get("name", "") for s in learning_result.skills_created]

        # Store in memory (only if useful)
        if self._should_store_in_memory(state):
            from genesis_ai.core.memory.engine import MemoryEngine
            memory = MemoryEngine(self.db)
            memory.store_memory(
                f"User: {state.raw_input[:200]}",
                "SHORT_TERM",
                {"user_id": state.user_id, "intent": state.msg_type, "role": "user"},
            )
            memory.store_memory(
                f"Assistant: {state.response_text[:200]}",
                "SHORT_TERM",
                {"user_id": state.user_id, "intent": state.msg_type, "role": "assistant"},
            )

        state.mark_stage("LEARN")
        return state

    def run_full_pipeline(self, state: CognitiveState) -> CognitiveState:
        """Run the complete cognitive pipeline.

        This is the main entry point that replaces the hardcoded routing
        in main.py. Each stage is optional based on complexity.
        """
        # Stage 1: PERCEIVE (always)
        state = self.perceive(state)

        # Progressive complexity: skip heavy stages for trivial inputs
        if state.complexity == Complexity.TRIVIAL:
            state = self.understand(state)
            state = self.decide(state)
            state = self.act(state)
            state.total_duration = time.time() - state.start_time
            return state

        # Stage 2: UNDERSTAND
        state = self.understand(state)

        # Stage 3: ASSESS KNOWLEDGE
        state = self.assess_knowledge(state)

        # Stage 4: DECIDE
        state = self.decide(state)

        # Stage 5: ACT
        state = self.act(state)

        # Stage 6: VERIFY (skip for simple tasks)
        if state.complexity in (Complexity.MODERATE, Complexity.COMPLEX):
            state = self.verify(state)

            # Revision loop (max 1 revision)
            if state.needs_revision and state.response_text:
                state.needs_revision = False
                state.evaluation_issues.clear()
                state = self.act(state)  # try again with different approach
                state = self.verify(state)

        # Stage 7: LEARN (always for non-trivial)
        state = self.learn(state)

        state.total_duration = time.time() - state.start_time
        return state

    # ── Action Handlers ────────────────────────────────────────────────

    def _act_respond(self, state: CognitiveState) -> CognitiveState:
        """Generate a response based on current knowledge."""
        if state.response_text:
            return state  # already have a response

        # For conversation/casual: use conversation engine
        if state.goal_type == GoalType.CONVERSATION:
            from genesis_ai.core.ai_responder import get_casual_response
            state.response_text = get_casual_response(
                state.raw_input, state.detected_language, state.conversation_history
            )
            state.msg_type = "CASUAL"
            state.confidence_score = 1.0
            return state

        # For identity: use identity response
        if state.goal_type == GoalType.IDENTITY:
            state.response_text = self._identity_response(state.detected_language)
            state.msg_type = "IDENTITY"
            state.confidence_score = 1.0
            return state

        # For code: try local generation
        if state.goal_type == GoalType.CODE:
            from genesis_ai.core.code.generator import CodeGenerator
            gen = CodeGenerator()
            code = gen.generate(state.raw_input)
            if code:
                lang_name = state.entities.get("languages", ["python"])[0]
                topic = state.raw_input.title()
                state.response_text = f"Here is the code for {topic}:\n\n```\n{code}\n```"
                state.msg_type = "CODE"
                state.confidence_score = 0.9
                return state

        # For factual/research with known knowledge: synthesize
        if state.knowledge_status == KnowledgeStatus.KNOWN and state.local_knowledge:
            state.response_text = self._synthesize_from_knowledge(state)
            state.msg_type = "FACTUAL"
            return state

        # Default: generate from evidence if available
        if state.evidence:
            state.response_text = self._synthesize_from_evidence(state)
            state.msg_type = "FACTUAL"
            return state

        # Fallback
        state.response_text = self._fallback_response(state)
        return state

    def _act_recall(self, state: CognitiveState) -> CognitiveState:
        """Recall from local knowledge and memory."""
        # Already assessed in assess_knowledge
        if state.local_knowledge:
            state.response_text = self._synthesize_from_knowledge(state)
            state.knowledge_status = KnowledgeStatus.KNOWN
        elif state.relevant_memories:
            state.response_text = self._synthesize_from_memories(state)
            state.knowledge_status = KnowledgeStatus.KNOWN
        elif state.relevant_experiences:
            state.response_text = self._synthesize_from_experiences(state)
            state.knowledge_status = KnowledgeStatus.KNOWN
        else:
            # Nothing found locally — need to search
            state.selected_action = DecisionAction.SEARCH
            state = self._act_search(state)
        return state

    def _act_search(self, state: CognitiveState) -> CognitiveState:
        """Search the web for information."""
        from genesis_ai.research.search.engine import WebSearchEngine
        from genesis_ai.core.ai_responder import build_search_queries, synthesize_response

        search = WebSearchEngine()
        queries = build_search_queries(state.raw_input, state.goal_type.value.upper())
        state.research_queries = queries

        all_results = []
        for q in queries[:3]:
            results = search.search(q, max_results=3)
            if results:
                all_results.extend(results)

        if all_results:
            state.sources_used = [
                r.source_name for r in all_results if r.source_name
            ]
            state.evidence = [
                {
                    "claim": r.snippet,
                    "source": r.source_name,
                    "url": r.url,
                    "title": r.title,
                }
                for r in all_results if r.snippet
            ]
            state.knowledge_status = KnowledgeStatus.UNVERIFIED
            state.response_text = synthesize_response(
                state.raw_input,
                all_results,
                state.detected_language,
                state.goal_type.value.upper(),
            )
        else:
            state.knowledge_status = KnowledgeStatus.UNKNOWN
            state.response_text = self._fallback_response(state)

        return state

    def _act_deep_research(self, state: CognitiveState) -> CognitiveState:
        """Deep research with multi-source verification."""
        # For now, delegate to search with more sources
        state = self._act_search(state)

        # If we got evidence, try to verify
        if state.evidence and len(state.evidence) > 1:
            from genesis_ai.core.contradiction.engine import ContradictionEngine
            from genesis_ai.core.comparison.engine import ComparisonEngine

            claims = [
                {"text": e["claim"], "source_name": e.get("source", "")}
                for e in state.evidence
            ]

            # Check contradictions
            contra = ContradictionEngine()
            contra_result = contra.detect(claims)
            state.contradictions = [
                {"severity": c.severity, "resolution": c.resolution}
                for c in (contra_result.contradictions if contra_result else [])
            ]

            # Compare sources
            comp = ComparisonEngine()
            comp_result = comp.compare(state.evidence)
            state.comparison_result = {
                "best": comp_result.best_approach if comp_result else None,
                "approaches": len(comp_result.approaches) if comp_result else 0,
            }

        return state

    def _act_reason(self, state: CognitiveState) -> CognitiveState:
        """Apply reasoning to the problem."""
        from genesis_ai.core.reasoning.engine import ReasoningEngine
        reasoning = ReasoningEngine(self.db)

        result = reasoning.reason(
            state.raw_input,
            context={"constraints": state.constraints},
        )
        state.reasoning_result = {
            "reasoning": result.reasoning if result else "",
            "conclusions": result.conclusions if result else [],
            "confidence": result.confidence if result else 0.0,
        }

        # If reasoning produced a conclusion, use it
        if result and result.conclusions:
            state.response_text = "\n".join(result.conclusions)
            state.knowledge_status = KnowledgeStatus.KNOWN

        return state

    def _act_clarify(self, state: CognitiveState) -> CognitiveState:
        """Ask for clarification when information is insufficient."""
        lang = state.detected_language
        clarify_msgs = {
            "hindi": "मुझे आपके प्रश्न को समझने के लिए थोड़ी और जानकारी चाहिए। कृपया और विस्तार से बताइए।",
            "hinglish": "Mujhe thoda aur detail chahiye. Kya aap aur bata sakte hain?",
            "english": "I need a bit more information to help you. Could you provide more details?",
        }
        state.response_text = clarify_msgs.get(lang, clarify_msgs["english"])
        state.msg_type = "CLARIFICATION"
        state.confidence_score = 0.3
        return state

    def _act_tool(self, state: CognitiveState) -> CognitiveState:
        """Use a tool (calculator, code execution, etc.)."""
        # Delegate to tool engine
        return state

    # ── Helper Methods ────────────────────────────────────────────────

    def _detect_language(self, msg: str) -> str:
        """Detect language using structural patterns."""
        import re
        hindi_chars = len(re.findall(r"[\u0900-\u097F]", msg))
        total_chars = len(re.findall(r"\w", msg))
        if total_chars == 0:
            return "english"
        hindi_ratio = hindi_chars / total_chars
        if hindi_ratio > 0.5:
            return "hindi"
        elif hindi_ratio > 0.2:
            return "hinglish"
        return "english"

    def _is_identity_question(self, msg: str) -> bool:
        """Detect identity questions using structural patterns."""
        msg_lower = msg.lower().strip()
        self_refs = ["genesis", "yourself", "tum", "aap", "tera", "tumhara",
                      "apna", "your", "you"]
        id_q_words = ["who", "what", "kaun", "kya", "name", "naam"]
        has_self = any(w in msg_lower for w in self_refs)
        has_q = any(w in msg_lower for w in id_q_words)
        return has_self and has_q

    def _is_time_sensitive(self, state: CognitiveState) -> bool:
        """Check if the topic is time-sensitive (structural, not content-based)."""
        time_words = ["latest", "current", "today", "now", "recent",
                      "2024", "2025", "2026", "aajkal", "abhi"]
        return any(w in state.raw_input.lower() for w in time_words)

    def _has_raw_research_text(self, state: CognitiveState) -> bool:
        """Check if response contains raw research text (not synthesized)."""
        if not state.evidence or not state.response_text:
            return False
        # Check if any evidence snippet appears verbatim in response
        for e in state.evidence:
            snippet = e.get("claim", "")
            if snippet and len(snippet) > 50 and snippet in state.response_text:
                return True
        return False

    def _synthesize_from_knowledge(self, state: CognitiveState) -> str:
        """Synthesize a response from local knowledge."""
        from genesis_ai.core.ai_responder import synthesize_response
        # Convert local knowledge to result-like objects
        results = []
        for k in state.local_knowledge[:3]:
            results.append(type("R", (), {
                "snippet": k.get("content", k.get("claim", "")),
                "source_name": k.get("source", "local"),
                "url": k.get("url", ""),
                "title": k.get("topic", ""),
            })())
        if results:
            return synthesize_response(
                state.raw_input, results, state.detected_language,
                state.goal_type.value.upper(),
            )
        return self._fallback_response(state)

    def _synthesize_from_memories(self, state: CognitiveState) -> str:
        """Synthesize a response from relevant memories."""
        if state.relevant_memories:
            return state.relevant_memories[0].get("content", "")
        return self._fallback_response(state)

    def _synthesize_from_experiences(self, state: CognitiveState) -> str:
        """Synthesize a response from relevant experiences."""
        if state.relevant_experiences:
            exp = state.relevant_experiences[0]
            return exp.get("solution_summary", exp.get("task_description", ""))
        return self._fallback_response(state)

    def _synthesize_from_evidence(self, state: CognitiveState) -> str:
        """Synthesize a response from web evidence."""
        from genesis_ai.core.ai_responder import synthesize_response
        results = []
        for e in state.evidence[:5]:
            results.append(type("R", (), {
                "snippet": e.get("claim", ""),
                "source_name": e.get("source", ""),
                "url": e.get("url", ""),
                "title": e.get("title", ""),
            })())
        if results:
            return synthesize_response(
                state.raw_input, results, state.detected_language,
                state.goal_type.value.upper(),
            )
        return self._fallback_response(state)

    def _fallback_response(self, state: CognitiveState) -> str:
        """Generate a fallback response when nothing else works."""
        lang = state.detected_language
        msgs = {
            "hindi": "मुझे इस विषय पर पर्याप्त जानकारी नहीं है। कृपया और विस्तार से बताइए।",
            "hinglish": "Mujhe is topic pe enough info nahi hai. Thoda aur batao?",
            "english": "I don't have enough information on this topic. Could you provide more details?",
        }
        return msgs.get(lang, msgs["english"])

    def _identity_response(self, lang: str) -> str:
        """Generate identity response."""
        msgs = {
            "hindi": "मैं **Genesis AI** हूँ — आपका personal AI assistant! मैं research, coding, aur conversation में help कर सकता हूँ।",
            "hinglish": "Main **Genesis AI** hoon — aapka personal AI assistant! Research, coding, aur conversation mein help kar sakta hoon.",
            "english": "I'm **Genesis AI** — your personal AI assistant! I can help with research, coding, and conversation.",
        }
        return msgs.get(lang, msgs["english"])

    def _extract_generalizations(self, state: CognitiveState) -> list[str]:
        """Extract generalizable lessons from this experience."""
        generalizations = []
        if state.needs_revision:
            generalizations.append(
                f"Task type '{state.goal_type.value}' with complexity '{state.complexity.value}' "
                f"required revision. Consider: {', '.join(state.evaluation_issues[:2])}"
            )
        if state.contradictions:
            generalizations.append(
                "Contradictory sources found. Always cross-verify before answering."
            )
        if state.knowledge_status == KnowledgeStatus.OUTDATED:
            generalizations.append(
                "Knowledge was outdated. Time-sensitive topics need fresh verification."
            )
        return generalizations

    def _should_store_in_memory(self, state: CognitiveState) -> bool:
        """Decide if this interaction is worth storing in memory."""
        # Don't store trivial interactions
        if state.complexity == Complexity.TRIVIAL:
            return False
        # Don't store if response was poor
        if state.needs_revision:
            return False
        # Store if it involved research or reasoning
        if state.selected_action in (
            DecisionAction.SEARCH,
            DecisionAction.DEEP_RESEARCH,
            DecisionAction.REASON,
        ):
            return True
        # Store if it was a code task
        if state.goal_type == GoalType.CODE:
            return True
        return False
