"""ContextManager — structured conversation state for multi-turn understanding.

Manages:
- Topic tracking with transitions
- Reference resolution (pronouns: this, that, isko, woh, etc.)
- User goal detection and transitions
- Context relevance scoring
- Context decay over time
- Short-term vs long-term memory separation
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════════════════
# USER GOAL TYPES
# ═══════════════════════════════════════════════════════

class UserGoal:
    """User goal categories — distinct from intent."""
    INFORMATION = "information"         # wants to know facts
    EXPLANATION = "explanation"         # wants to understand how/why
    LEARNING = "learning"              # wants to learn a topic
    CREATION = "creation"              # wants to create something
    MODIFICATION = "modification"      # wants to change something existing
    COMPARISON = "comparison"          # wants to compare options
    TROUBLESHOOTING = "troubleshooting" # wants to fix a problem
    CODING = "coding"                  # wants code written
    RESEARCH = "research"              # wants deep investigation
    RECOMMENDATION = "recommendation"  # wants suggestions
    PLANNING = "planning"              # wants to plan something
    CONTINUATION = "continuation"      # wants to continue previous topic
    CORRECTION = "correction"          # correcting previous response
    CONFIRMATION = "confirmation"      # confirming understanding
    CLARIFICATION = "clarification"    # asking for clarification
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════
# CONVERSATION TURN
# ═══════════════════════════════════════════════════════

@dataclass
class ConversationTurn:
    """Single turn in a conversation."""
    role: str                    # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    topic: str = ""
    entities: dict = field(default_factory=dict)
    intent: str = ""
    goal: str = ""
    resolved_references: dict = field(default_factory=dict)
    relevance_score: float = 1.0


# ═══════════════════════════════════════════════════════
# CONVERSATION CONTEXT
# ═══════════════════════════════════════════════════════

@dataclass
class ConversationContext:
    """Structured conversation state — persisted across turns."""
    conversation_id: str = ""
    current_topic: str = ""
    previous_topic: str = ""
    active_goal: str = UserGoal.UNKNOWN
    previous_goal: str = UserGoal.UNKNOWN
    recent_entities: dict = field(default_factory=dict)
    recent_concepts: list[str] = field(default_factory=list)
    previous_user_request: str = ""
    previous_assistant_result: str = ""
    pending_task: str = ""
    unresolved_question: str = ""
    current_intent: str = ""
    confidence: float = 0.0
    context_age: float = 0.0
    user_constraints: list[str] = field(default_factory=list)
    topic_stack: list[str] = field(default_factory=list)
    message_count: int = 0
    last_entity_mentioned: str = ""
    reference_map: dict = field(default_factory=dict)
    correction_pending: bool = False
    clarification_needed: bool = False
    turns: list[ConversationTurn] = field(default_factory=list)


# ═══════════════════════════════════════════════════════
# REFERENCE RESOLUTION
# ═══════════════════════════════════════════════════════

# English pronouns
_EN_PRONOUNS = {"this", "that", "it", "them", "these", "those", "its", "their"}

# Hindi/Hinglish pronouns
_HI_PRONOUNS = {
    "isko": "this", "usko": "that", "yeh": "this", "woh": "that",
    "ye": "this", "unhe": "them", "inhe": "them", "uska": "its",
    "iska": "this", "usme": "in that", "isme": "in this",
    "usse": "with that", "isse": "with this",
    "uske": "of that", "iske": "of this",
}

# Combined
_ALL_PRONOUNS = set(_EN_PRONOUNS) | set(_HI_PRONOUNS.keys())

# Informational query markers (should NOT resolve references to creative patterns)
_INFO_MARKERS = [
    "what is", "what are", "what was", "what's",
    "how does", "how do", "how did", "how is",
    "who is", "who are", "who was",
    "where is", "where are",
    "when was", "when did",
    "why does", "why do", "why is",
    "tell me about", "explain", "describe",
    "kya hai", "kya hain", "kya hota hai", "kya hoti hai",
    "kaun hai", "kahan hai", "kab hua", "kyun hai",
    "kaise hota hai", "kaise kaam karta hai",
    "samjhao", "batao about", "meaning kya hai",
    "meaning samjhao", "definition",
]

# Topic change markers
_TOPIC_CHANGE_MARKERS = [
    "tell me about", "batao about", "discuss", "charcha karo",
    "let's talk about", "baat karo about", "switch to",
    "move on to", "new topic", "naya topic",
    "actually", "waise", "by the way", "vaise",
    "forget that", "leave that", "chhodo",
]

# Continuation markers
_CONTINUATION_MARKERS = [
    "and", "also", "aur", "bhi", "plus", "moreover",
    "then", "uske baad", "after that", "next",
    "continue", "aage badho", "go on", "proceed",
    "what about", "kya about", "how about",
]

# Correction markers
_CORRECTION_MARKERS = [
    "no", "nahi", "nope", "wrong", "galat",
    "i meant", "maine kaha", "i meant to say",
    "actually", "asal mein", "vaise",
    "not that", "woh nahi", "not this",
    "correct", "theek hai", "right",
    "change", "badlo", "modify", "update",
]

# Clarification request markers
_CLARIFICATION_MARKERS = [
    "what do you mean", "matlab kya", "kya kehna chahte",
    "can you clarify", "elaborate",
    "i don't understand", "samajh nahi aaya",
    "what exactly", "precisely kya",
]


# ═══════════════════════════════════════════════════════
# CONTEXT MANAGER
# ═══════════════════════════════════════════════════════

class ContextManager:
    """Manages conversation context across turns.

    This is the central context management system for Phase 2.
    It handles topic tracking, reference resolution, user goal detection,
    context relevance scoring, and context decay.
    """

    # Context decay rate: relevance decreases by this factor per turn
    CONTEXT_DECAY_RATE = 0.85
    # Minimum relevance threshold for context to be considered
    MIN_RELEVANCE = 0.15
    # Maximum turns to keep in short-term context
    MAX_SHORT_TERM_TURNS = 30
    # Time threshold for decay (seconds) — older than this gets decayed
    TIME_DECAY_THRESHOLD = 300  # 5 minutes

    def __init__(self):
        self.contexts: dict[str, ConversationContext] = {}

    def get_context(self, user_id: str) -> ConversationContext:
        """Get or create conversation context for a user."""
        if user_id not in self.contexts:
            self.contexts[user_id] = ConversationContext(
                conversation_id=f"{user_id}_{int(time.time())}",
            )
        return self.contexts[user_id]

    def update_context(
        self,
        user_id: str,
        message: str,
        response: str,
        intent: str,
        goal: str,
        entities: dict,
        topic: str,
        confidence: float,
    ) -> ConversationContext:
        """Update conversation context after a turn."""
        ctx = self.get_context(user_id)
        now = time.time()

        # Create turn record
        turn = ConversationTurn(
            role="user",
            content=message,
            timestamp=now,
            topic=topic,
            entities=entities,
            intent=intent,
            goal=goal,
        )
        ctx.turns.append(turn)

        # Create assistant turn
        assistant_turn = ConversationTurn(
            role="assistant",
            content=response[:500] if response else "",
            timestamp=now,
            topic=topic,
        )
        ctx.turns.append(assistant_turn)

        # Trim old turns
        if len(ctx.turns) > self.MAX_SHORT_TERM_TURNS * 2:
            ctx.turns = ctx.turns[-(self.MAX_SHORT_TERM_TURNS * 2):]

        # Update topic
        if topic and topic != ctx.current_topic:
            ctx.previous_topic = ctx.current_topic
            if ctx.current_topic and ctx.current_topic != "general":
                ctx.topic_stack.append(ctx.current_topic)
            ctx.current_topic = topic

        # Update goal
        if goal and goal != UserGoal.UNKNOWN:
            ctx.previous_goal = ctx.active_goal
            ctx.active_goal = goal

        # Update entities
        for key, value in entities.items():
            if value:
                ctx.recent_entities[key] = value
                ctx.last_entity_mentioned = f"{key}:{value}"

        # Update reference map
        self._update_references(ctx, message)

        # Update request/response tracking
        ctx.previous_user_request = message
        ctx.previous_assistant_result = response[:300] if response else ""
        ctx.current_intent = intent
        ctx.confidence = confidence
        ctx.message_count += 1
        ctx.context_age = now - (ctx.turns[0].timestamp if ctx.turns else now)

        # Apply context decay to older turns
        self._apply_decay(ctx, now)

        return ctx

    def resolve_references(self, user_id: str, message: str) -> dict:
        """Resolve pronouns and references in a message.

        Returns a dict mapping pronouns to their resolved entities.
        """
        ctx = self.get_context(user_id)
        resolved = {}
        words = re.findall(r'\b\w+\b', message.lower())

        for word in words:
            if word in _ALL_PRONOUNS:
                # Try reference map first
                if word in ctx.reference_map:
                    resolved[word] = ctx.reference_map[word]
                # Fall back to last entity
                elif ctx.last_entity_mentioned:
                    resolved[word] = ctx.last_entity_mentioned

        return resolved

    def detect_topic(self, user_id: str, message: str, entities: dict) -> str:
        """Detect the current topic from message and entities.

        Returns the detected topic, or current topic if no change detected.
        Key principle: prefer CONTINUATION over new topic unless explicit switch.
        """
        ctx = self.get_context(user_id)
        msg_lower = message.lower()

        # Check for explicit topic change markers FIRST
        for marker in _TOPIC_CHANGE_MARKERS:
            if marker in msg_lower:
                idx = msg_lower.index(marker) + len(marker)
                remaining = msg_lower[idx:].strip()
                if remaining and len(remaining) > 2:
                    return remaining[:50]

        # Check for topic from entities
        if entities:
            for key in ("topic", "subject", "about", "language", "tool", "technology"):
                if key in entities and entities[key]:
                    return entities[key]

        # Check for continuation markers — keep current topic
        for marker in _CONTINUATION_MARKERS:
            if marker in msg_lower:
                return ctx.current_topic or "general"

        # Check for pronouns — keep current topic
        import re
        pronouns = {"it", "them", "this", "that", "isko", "usko", "ye", "woh", "isme", "usme", "iska", "uska"}
        words = set(re.findall(r'\b\w+\b', msg_lower))
        if words & pronouns:
            return ctx.current_topic or "general"

        # Extract topic from question patterns (before short-message check)
        topic_patterns = [
            r'(?:what is|who is|tell me about|explain|ke baare mein)\s+(.+?)(?:\?|$)',
            r'(?:how does|how do|kaise)\s+(.+?)(?:\s+work|\?|$)',
            r'(.+?)\s+(?:kya hai|kaun hai|kaise hai|kya hota hai)',
            r'(?:ab|now)\s+(.+?)\s+(?:samjhao|batao|seekho)',
        ]
        for p in topic_patterns:
            m = re.search(p, msg_lower)
            if m:
                topic = m.group(1).strip()
                topic = re.sub(r'\b(a|an|the|ek|ye|woh|iska|uska|ab)\b', '', topic).strip()
                if 2 < len(topic) < 40:
                    if ctx.current_topic and ctx.current_topic != "general":
                        current_words = set(ctx.current_topic.lower().split())
                        topic_words = set(topic.split())
                        if current_words & topic_words:
                            return ctx.current_topic
                    return topic

        # Short messages (<=5 words) with active topic → continue topic
        word_count = len(re.findall(r'\b\w+\b', msg_lower))
        if word_count <= 5 and ctx.current_topic and ctx.current_topic != "general":
            return ctx.current_topic

        # Default: keep current topic
        return ctx.current_topic or "general"

    def detect_user_goal(
        self,
        user_id: str,
        message: str,
        intent: str,
        resolved_refs: dict,
    ) -> str:
        """Detect the user's goal from message and context.

        The goal is distinct from intent — intent is what the message IS,
        goal is what the user WANTS to achieve.
        """
        ctx = self.get_context(user_id)
        msg_lower = message.lower()

        # Check for correction
        for marker in _CORRECTION_MARKERS:
            if marker in msg_lower:
                return UserGoal.CORRECTION

        # Check for clarification request
        for marker in _CLARIFICATION_MARKERS:
            if marker in msg_lower:
                return UserGoal.CLARIFICATION

        # Check for continuation markers
        for marker in _CONTINUATION_MARKERS:
            if marker in msg_lower:
                if ctx.active_goal != UserGoal.UNKNOWN:
                    return UserGoal.CONTINUATION
                # Even without previous goal, short continuation → CONTINUATION
                word_count = len(re.findall(r'\b\w+\b', msg_lower))
                if word_count <= 4:
                    return UserGoal.CONTINUATION

        # Check for pronouns — implies continuation/modification
        if resolved_refs:
            return UserGoal.MODIFICATION

        # Short messages with active goal → continue that goal
        word_count = len(re.findall(r'\b\w+\b', msg_lower))
        if word_count <= 4 and ctx.active_goal != UserGoal.UNKNOWN:
            return UserGoal.CONTINUATION

        # Detect from intent
        intent_goal_map = {
            "creative": UserGoal.CREATION,
            "code": UserGoal.CODING,
            "factual": UserGoal.INFORMATION,
            "research": UserGoal.RESEARCH,
            "explain": UserGoal.EXPLANATION,
            "fix": UserGoal.TROUBLESHOOTING,
            "compare": UserGoal.COMPARISON,
            "conversation": UserGoal.INFORMATION,
        }
        if intent in intent_goal_map:
            return intent_goal_map[intent]

        # Detect from message patterns
        if any(w in msg_lower for w in ["how do i", "kaise karu", "help me", "madad karo"]):
            return UserGoal.LEARNING
        if any(w in msg_lower for w in ["write", "create", "make", "banao", "likho"]):
            return UserGoal.CREATION
        if any(w in msg_lower for w in ["fix", "debug", "repair", "theek karo"]):
            return UserGoal.TROUBLESHOOTING
        if any(w in msg_lower for w in ["suggest", "recommend", "batao", "dikhao"]):
            return UserGoal.RECOMMENDATION
        if any(w in msg_lower for w in ["plan", "yojana", "strategy"]):
            return UserGoal.PLANNING

        return UserGoal.UNKNOWN

    def is_contextually_relevant(
        self,
        user_id: str,
        message: str,
        turn: ConversationTurn,
    ) -> float:
        """Score how relevant a previous turn is to the current message.

        Returns a score between 0.0 and 1.0.
        """
        ctx = self.get_context(user_id)
        now = time.time()

        # Base relevance from recency
        age_seconds = now - turn.timestamp
        recency_score = max(0.0, 1.0 - (age_seconds / (self.TIME_DECAY_THRESHOLD * 10)))

        # Topic match
        topic_match = 1.0 if turn.topic == ctx.current_topic else 0.3

        # Entity overlap
        current_words = set(re.findall(r'\b[a-z]{3,}\b', message.lower()))
        turn_words = set(re.findall(r'\b[a-z]{3,}\b', turn.content.lower()))
        entity_overlap = len(current_words & turn_words) / max(len(current_words | turn_words), 1)

        # Combined relevance
        relevance = (recency_score * 0.4 + topic_match * 0.3 + entity_overlap * 0.3)
        return max(0.0, min(1.0, relevance))

    def get_relevant_context(
        self,
        user_id: str,
        message: str,
        max_turns: int = 10,
    ) -> list[ConversationTurn]:
        """Get the most relevant previous turns for the current message.

        Does NOT blindly send entire history — selects relevant context.
        """
        ctx = self.get_context(user_id)
        if not ctx.turns:
            return []

        # Score each turn
        scored = []
        for turn in ctx.turns:
            if turn.role == "user":  # Only score user turns
                relevance = self.is_contextually_relevant(user_id, message, turn)
                if relevance >= self.MIN_RELEVANCE:
                    scored.append((relevance, turn))

        # Sort by relevance descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Return top N
        return [turn for _, turn in scored[:max_turns]]

    def detect_topic_switch(self, user_id: str, message: str) -> bool:
        """Detect if the user is switching topics."""
        ctx = self.get_context(user_id)
        msg_lower = message.lower()

        # Explicit topic change markers
        for marker in _TOPIC_CHANGE_MARKERS:
            if marker in msg_lower:
                return True

        # Check if message is about a completely different topic
        if ctx.current_topic and ctx.current_topic != "general":
            current_words = set(ctx.current_topic.lower().split())
            message_words = set(re.findall(r'\b[a-z]{3,}\b', msg_lower))
            overlap = len(current_words & message_words)
            if overlap == 0 and len(message_words) > 3:
                # No topic overlap — likely a topic switch
                return True

        return False

    def should_ask_clarification(
        self,
        user_id: str,
        message: str,
        intent_confidence: float,
    ) -> bool:
        """Determine if Genesis should ask for clarification.

        Returns True if:
        - The message is very ambiguous
        - There's no clear active object for pronouns
        - Confidence is very low
        """
        ctx = self.get_context(user_id)
        msg_lower = message.lower()

        # Very short messages with pronouns but no clear referent
        words = re.findall(r'\b\w+\b', msg_lower)
        has_pronoun = any(w in _ALL_PRONOUNS for w in words)
        if has_pronoun and not ctx.last_entity_mentioned:
            return True

        # Very low confidence
        if intent_confidence < 0.3:
            return True

        # Vague requests with no context
        vague_patterns = [
            r'^(make it better|fix it|change it|improve it)$',
            r'^(isko|usko|yeh|woh|this|that|it)\s*$',
            r'^(do it|karo|banao)\s*$',
        ]
        for p in vague_patterns:
            if re.match(p, msg_lower.strip()):
                if not ctx.previous_user_request:
                    return True

        return False

    def _update_references(self, ctx: ConversationContext, message: str):
        """Update the reference map with pronouns from the current message."""
        words = re.findall(r'\b\w+\b', message.lower())

        for word in words:
            if word in _HI_PRONOUNS:
                if ctx.last_entity_mentioned:
                    ctx.reference_map[word] = ctx.last_entity_mentioned
                    eng = _HI_PRONOUNS[word]
                    ctx.reference_map[eng] = ctx.last_entity_mentioned

        if ctx.last_entity_mentioned:
            for pronoun in _EN_PRONOUNS:
                ctx.reference_map[pronoun] = ctx.last_entity_mentioned

    def _apply_decay(self, ctx: ConversationContext, now: float):
        """Apply relevance decay to older turns."""
        for turn in ctx.turns:
            age_seconds = now - turn.timestamp
            if age_seconds > self.TIME_DECAY_THRESHOLD:
                turns_old = int(age_seconds / self.TIME_DECAY_THRESHOLD)
                turn.relevance_score *= (self.CONTEXT_DECAY_RATE ** turns_old)
                turn.relevance_score = max(0.0, turn.relevance_score)

    def get_topic_history(self, user_id: str, max_topics: int = 5) -> list[str]:
        """Get recent topic history."""
        ctx = self.get_context(user_id)
        topics = []
        for turn in reversed(ctx.turns):
            if turn.topic and turn.topic not in topics:
                topics.append(turn.topic)
                if len(topics) >= max_topics:
                    break
        return list(reversed(topics))

    def get_short_term_summary(self, user_id: str) -> dict:
        """Get a summary of the short-term conversation context."""
        ctx = self.get_context(user_id)
        return {
            "current_topic": ctx.current_topic,
            "previous_topic": ctx.previous_topic,
            "active_goal": ctx.active_goal,
            "previous_goal": ctx.previous_goal,
            "recent_entities": ctx.recent_entities,
            "last_entity": ctx.last_entity_mentioned,
            "message_count": ctx.message_count,
            "previous_request": ctx.previous_user_request[:200],
            "previous_response": ctx.previous_assistant_result[:200],
            "pending_task": ctx.pending_task,
            "correction_pending": ctx.correction_pending,
            "clarification_needed": ctx.clarification_needed,
            "topic_stack": ctx.topic_stack[-5:],
        }
