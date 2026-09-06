from dataclasses import dataclass, field
from typing import Dict, List, Optional
import time


@dataclass
class ContextState:
    current_topic: str = "general"
    topic_stack: List[str] = field(default_factory=list)
    entities: Dict[str, str] = field(default_factory=dict)
    references: Dict[str, str] = field(default_factory=dict)
    conversation_mode: str = "casual"
    last_entity_mentioned: Optional[str] = None
    last_topic_mentioned: Optional[str] = None
    message_count: int = 0
    context_updated_at: float = field(default_factory=time.time)
    pending_action: Optional[str] = None


class ContextEngine:
    def __init__(self):
        self.state = ContextState()
        self.history: List[Dict] = []
        self.reference_map: Dict[str, str] = {}
        self.entity_history: List[Dict] = []
        self.topic_transitions: List[Dict] = []

    def update_context(self, message: str, intent: dict) -> ContextState:
        self.state.message_count += 1
        self.state.context_updated_at = time.time()
        intent_type = intent.get("intent", "UNKNOWN")
        entities = intent.get("entities", {})
        self._update_entities(entities)
        self._update_references(message, entities)
        self._update_topic(entities, intent_type)
        self._update_conversation_mode(intent_type)
        self._update_pending_action(intent_type, entities)
        self.history.append({
            "message": message,
            "intent": intent_type,
            "entities": entities,
            "timestamp": time.time(),
            "context_snapshot": self._snapshot(),
        })
        if len(self.history) > 50:
            self.history = self.history[-50:]
        return self.state

    def get_current_context(self) -> ContextState:
        return self.state

    def resolve_reference(self, pronoun: str) -> Optional[str]:
        pronoun_lower = pronoun.lower().strip()
        direct_map = {
            "isko": None,
            "usko": None,
            "yeh": None,
            "woh": None,
            "ye": None,
            "this": None,
            "that": None,
            "it": None,
            "them": None,
            "unhe": None,
            "inhe": None,
        }
        if pronoun_lower in direct_map:
            resolved = self.reference_map.get(pronoun_lower)
            if resolved:
                return resolved
        if self.state.last_entity_mentioned:
            return self.state.last_entity_mentioned
        if self.state.entities:
            values = list(self.state.entities.values())
            if values:
                return values[-1]
        return None

    def clear_context(self):
        self.state = ContextState()
        self.reference_map.clear()
        self.entity_history.clear()

    def push_topic(self, topic: str):
        if self.state.current_topic != "general":
            self.state.topic_stack.append(self.state.current_topic)
        self.state.current_topic = topic
        self.topic_transitions.append({
            "from": self.state.topic_stack[-1] if self.state.topic_stack else "general",
            "to": topic,
            "timestamp": time.time(),
        })

    def pop_topic(self) -> Optional[str]:
        if self.state.topic_stack:
            prev = self.state.current_topic
            self.state.current_topic = self.state.topic_stack.pop()
            return prev
        return None

    def get_topic_history(self) -> List[str]:
        topics = [t["to"] for t in self.topic_transitions[-10:]]
        return topics

    def _update_entities(self, entities: Dict[str, str]):
        for key, value in entities.items():
            if value:
                self.state.entities[key] = value
                self.entity_history.append({
                    "key": key,
                    "value": value,
                    "timestamp": time.time(),
                })
                self.state.last_entity_mentioned = f"{key}:{value}"

    def _update_references(self, message: str, entities: Dict[str, str]):
        hinglish_pronouns = {
            "isko": "this",
            "usko": "that",
            "yeh": "this",
            "woh": "that",
            "ye": "this",
            "unhe": "them",
            "inhe": "them",
            "uska": "its",
            "iska": "this",
        }
        for word in message.lower().split():
            clean = word.strip(".,!?;:'\"()")
            if clean in hinglish_pronouns:
                resolved = self.state.last_entity_mentioned
                if resolved:
                    self.reference_map[clean] = resolved
                    self.reference_map[hinglish_pronouns[clean]] = resolved
        if self.state.last_entity_mentioned:
            for eng_pronoun in ["this", "that", "it", "them"]:
                self.reference_map[eng_pronoun] = self.state.last_entity_mentioned

    def _update_topic(self, entities: Dict[str, str], intent_type: str):
        topic_from_entity = entities.get("topic")
        if topic_from_entity:
            if topic_from_entity != self.state.current_topic:
                self.push_topic(topic_from_entity)
            self.state.last_topic_mentioned = topic_from_entity
        elif intent_type == "QUESTION" and self.state.last_topic_mentioned:
            if self.state.current_topic == "general":
                self.push_topic(self.state.last_topic_mentioned)

    def _update_conversation_mode(self, intent_type: str):
        mode_map = {
            "GREETING": "greeting",
            "TASK_REQUEST": "task",
            "QUESTION": "question",
            "CASUAL": "casual",
            "FEEDBACK_POSITIVE": "casual",
            "FEEDBACK_NEGATIVE": "task",
            "COMMAND": "task",
            "REFLECTION": "reflection",
        }
        new_mode = mode_map.get(intent_type, "casual")
        if new_mode != self.state.conversation_mode:
            self.state.conversation_mode = new_mode

    def _update_pending_action(self, intent_type: str, entities: Dict[str, str]):
        if intent_type == "TASK_REQUEST":
            self.state.pending_action = entities.get("topic", "general_task")
        elif intent_type == "COMMAND":
            self.state.pending_action = "command_pending"
        elif intent_type == "FEEDBACK_NEGATIVE":
            self.state.pending_action = "correction_pending"
        elif intent_type == "FEEDBACK_POSITIVE":
            self.state.pending_action = None

    def _snapshot(self) -> Dict:
        return {
            "topic": self.state.current_topic,
            "mode": self.state.conversation_mode,
            "entities": dict(self.state.entities),
            "message_count": self.state.message_count,
        }
