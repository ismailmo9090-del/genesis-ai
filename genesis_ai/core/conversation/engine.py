from typing import Dict, Optional, List
import time
import json
import re

from genesis_ai.database.db import DatabaseManager
from genesis_ai.core.conversation.intent import IntentEngine, IntentResult
from genesis_ai.core.conversation.context import ContextEngine, ContextState
from genesis_ai.core.memory.engine import MemoryEngine


class ConversationEngine:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.intent_engine = IntentEngine()
        self.context_engine = ContextEngine()
        self.memory_engine = MemoryEngine(db)
        self.user_conversation_log: Dict[str, Dict] = {}
        self._ensure_tables()

    def _ensure_tables(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS conversation_log (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                intent TEXT,
                entities TEXT,
                context_snapshot TEXT,
                timestamp REAL NOT NULL
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS conversation_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                started_at REAL NOT NULL,
                ended_at REAL
            )
        """)

    def _detect_language(self, message: str) -> str:
        """Detect if message is English, Hindi (Devanagari), or Hinglish."""
        has_devanagari = bool(re.search(r'[\u0900-\u097F]', message))
        hindi_words = {'kya', 'hai', 'kaun', 'kaise', 'kyu', 'kyun', 'kab', 'kahan', 'yahan',
                       'wahan', 'ye', 'woh', 'yeh', 'tum', 'aap', 'hum', 'main', 'mein',
                       'mera', 'tera', 'uska', 'iska', 'banao', 'bana', 'karo', 'kar',
                       'mat', 'na', 'bhi', 'se', 'ko', 'ka', 'ki', 'ke', 'me', 'pe',
                       'par', 'aur', 'ya', 'to', 'phir', 'ab', 'yahi', 'wahi', 'sab',
                       'kuch', 'koi', 'nahi', 'nahin', 'haan', 'ji', 'sir', 'madam',
                       'accha', 'badhiya', 'theek', 'sahi', 'galat', 'help', 'madad',
                       'batao', 'samjhao', 'dikhao', 'chalo', 'ruk', 'band', 'save',
                       'search', 'find', 'tell', 'what', 'how', 'why', 'where', 'when',
                       'who', 'which', 'can', 'do', 'does', 'is', 'are', 'was', 'were'}
        words = re.findall(r'[a-zA-Z\u0900-\u097F]+', message.lower())
        hindi_count = sum(1 for w in words if w in hindi_words or re.match(r'[\u0900-\u097F]+', w))
        english_count = sum(1 for w in words if w.isascii() and w.isalpha())
        total = len(words) if words else 1
        if has_devanagari:
            return 'hindi'
        if hindi_count / total > 0.4:
            return 'hinglish'
        if english_count / total > 0.6:
            return 'english'
        return 'hinglish'

    def _get_response(self, lang: str, en: str, hi: str, mix: str) -> str:
        """Return response in the detected language."""
        if lang == 'english':
            return en
        elif lang == 'hindi':
            return hi
        return mix

    def process_message(self, user_id: str, message: str) -> Dict:
        intent_result = self.intent_engine.classify_intent(message)
        context = self.context_engine.update_context(message, {
            "intent": intent_result.intent,
            "confidence": intent_result.confidence,
            "entities": intent_result.entities,
        })
        self._store_message(user_id, "user", message, intent_result, context)
        self._store_user_memory(user_id, message, intent_result)
        response = self._generate_response(user_id, message, intent_result, context)
        self._store_message(user_id, "assistant", response["text"], None, context)
        self._store_assistant_memory(user_id, response["text"], intent_result)
        return {
            "text": response["text"],
            "intent": intent_result.intent,
            "confidence": intent_result.confidence,
            "entities": intent_result.entities,
            "context": {
                "topic": context.current_topic,
                "mode": context.conversation_mode,
                "message_count": context.message_count,
            },
            "response_type": response.get("type", "text"),
        }

    def _generate_response(self, user_id: str, message: str, intent: IntentResult, context: ContextState) -> Dict:
        handlers = {
            "GREETING": self._handle_greeting,
            "TASK_REQUEST": self._handle_task,
            "QUESTION": self._handle_question,
            "CASUAL": self._handle_casual,
            "FEEDBACK_POSITIVE": self._handle_feedback_positive,
            "FEEDBACK_NEGATIVE": self._handle_feedback_negative,
            "COMMAND": self._handle_command,
            "REFLECTION": self._handle_reflection,
        }
        handler = handlers.get(intent.intent, self._handle_casual)
        return handler(user_id, message, intent, context)

    def _handle_greeting(self, user_id: str, message: str, intent: IntentResult, context: ContextState) -> Dict:
        recent = self.memory_engine.get_recent_memories(3)
        recent_topics = [m["content"][:30] for m in recent if m.get("metadata", {}).get("user_id") == user_id]
        lang = self._detect_language(message)
        greetings = {
            'english': [
                "Hello! I'm Genesis AI, your personal assistant. How can I help you today?",
                "Hey there! Great to see you. What are we working on?",
                "Hi! Ready to help. What do you need?",
            ],
            'hindi': [
                "Namaste! Main Genesis AI hoon. Aapki kya madad kar sakta hoon?",
                "Namaskar! Kaise ho? Batao kya karna hai aaj?",
                "Hi! Main hoon Genesis AI. Kya help chahiye?",
            ],
            'hinglish': [
                "Hey! Welcome back. Kya plan hai aaj ka?",
                "Hello! Badhiya, batao kya kaam hai?",
                "Hi there! Genesis AI hoon, batao kya chahiye?",
            ],
        }
        response_text = greetings[lang][int(time.time()) % len(greetings[lang])]
        if recent_topics:
            response_text += f"\n\nI see we were discussing: {recent_topics[0]}. Want to continue?"
        return {"text": response_text, "type": "greeting"}

    def _handle_task(self, user_id: str, message: str, intent: IntentResult, context: ContextState) -> Dict:
        lang = self._detect_language(message)
        entities = intent.entities
        prog_lang = entities.get("programming_language", "")
        tool = entities.get("tool", "")
        topic = entities.get("topic", "")
        if prog_lang:
            return {
                "text": self._get_response(lang,
                    f"I can help you with {prog_lang}! Please share more details about what you'd like to build or fix.\n\n- What specific functionality do you need?\n- Is this a new project or existing code?\n- Any specific requirements?",
                    f"Haan, {prog_lang} mein help kar sakta hoon! Batao kya banana hai:\n\n- Kya functionality chahiye?\n- Naya project hai ya existing?\n- Koi specific requirements?",
                    f"Sure, {prog_lang} ke liye ready hoon! Batao kya karna hai:\n\n- Exact kya chahiye?\n- New project ya existing code?\n- Koi requirements?",
                ),
                "type": "task_clarification",
            }
        if tool:
            return {
                "text": self._get_response(lang,
                    f"Working with {tool}? Great! Tell me more about what you need:\n\n- Setup/configuration\n- Troubleshooting an issue\n- Best practices\n- Specific command or feature",
                    f"{tool} pe kaam karna hai? Batao kya chahiye:\n\n- Setup/configuration\n- Koi issue hai?\n- Best practices\n- Specific command",
                    f"{tool} use kar rahe ho? Batao kya help chahiye:\n\n- Setup\n- Problem solve\n- Best practices\n- Koi specific cheez",
                ),
                "type": "task_clarification",
            }
        if topic:
            topic_display = topic.replace("_", " ").title()
            return {
                "text": self._get_response(lang,
                    f"I understand you need help with {topic_display}. Let me know:\n\n- What specific aspect you need help with\n- Current situation or problem\n- Expected outcome",
                    f"{topic_display} mein help chahiye? Batao:\n\n- Kya specific cheez chahiye?\n- Abhi kya situation hai?\n- Kya expected result hai?",
                    f"{topic_display} samajhna hai? Batao:\n\n- Kya specific help chahiye?\n- Current situation kya hai?\n- Kya result chahiye?",
                ),
                "type": "task_clarification",
            }
        similar = self.memory_engine.search_memories(message, limit=3)
        if similar:
            memory_content = similar[0]["content"][:200]
            return {
                "text": self._get_response(lang,
                    f"I found a related memory that might help:\n\n\"{memory_content}...\"\n\nIs this relevant? Or tell me more about your current task.",
                    f"Mujhe ek related memory mili hai:\n\n\"{memory_content}...\"\n\nYe relevant hai? Ya apna current task batao.",
                    f"Ek related memory hai:\n\n\"{memory_content}...\"\n\nYe kaam ki hai? Ya apna task batao.",
                ),
                "type": "task_with_context",
            }
        return {
            "text": self._get_response(lang,
                "I'm ready to help with your task! Please provide more details:\n\n- What exactly do you need?\n- What have you tried so far?\n- Any specific requirements?",
                "Main ready hoon! Batao kya karna hai:\n\n- Exact kya chahiye?\n- Abhi tak kya try kiya?\n- Koi specific requirements?",
                "Ready hoon! Detail mein batao:\n\n- Kya chahiye exactly?\n- Kya try kiya hai?\n- Koi requirements?",
            ),
            "type": "task_clarification",
        }

    def _handle_question(self, user_id: str, message: str, intent: IntentResult, context: ContextState) -> Dict:
        lang = self._detect_language(message)
        entities = intent.entities
        topic = entities.get("topic", context.current_topic)
        similar = self.memory_engine.search_memories(message, limit=5)
        if similar:
            best = similar[0]
            score = best.get("relevance", 0)
            if score > 0.3:
                return {
                    "text": self._get_response(lang,
                        f"Based on what I know:\n\n{best['content']}\n\nIs this what you were looking for?",
                        f"Jo mujhe pata hai:\n\n{best['content']}\n\nYe sahi hai?",
                        f"Mere paas ye info hai:\n\n{best['content']}\n\nYe kaam aaya?",
                    ),
                    "type": "answer_from_memory",
                }
        if topic and topic != "general":
            topic_display = topic.replace("_", " ").title()
            return {
                "text": self._get_response(lang,
                    f"Regarding {topic_display} - I'm researching this topic to give you the best answer. Could you be more specific about what aspect you'd like to understand?",
                    f"{topic_display} ke baare mein - main research kar raha hoon. Batao kya specific cheez jaanna hai?",
                    f"{topic_display} ke baare mein - search kar raha hoon. Exact kya puchna hai?",
                ),
                "type": "question_clarification",
            }
        return {
            "text": self._get_response(lang,
                "That's a great question! I'm looking into this for you. Let me search my knowledge and the web for the best answer.",
                "Accha sawaal hai! Main iska jawab dhoondh raha hoon. Knowledge aur web dono check karunga.",
                "Good question! Main search kar raha hoon. Knowledge aur web se best jawab dunga.",
            ),
            "type": "question_open",
        }

    def _handle_casual(self, user_id: str, message: str, intent: IntentResult, context: ContextState) -> Dict:
        lang = self._detect_language(message)
        message_lower = message.lower()
        if any(w in message_lower for w in ["kaun hai", "who are you", "tum kya hai", "tumhara naam", "what are you"]):
            return {
                "text": self._get_response(lang,
                    "I'm Genesis AI - your personal AI assistant! I remember our conversations, help with tasks, and answer questions. How can I help you?",
                    "Main Genesis AI hoon - aapka personal AI assistant! Main conversation yaad rakhta hoon, tasks help karta hoon, aur questions ka jawab deta hoon. Aapki kya madad kar sakta hoon?",
                    "Main Genesis AI hoon - tumhara personal AI assistant! Conversation yaad rakhta hoon, tasks mein help karta hoon. Batao kya chahiye?",
                ),
                "type": "identity",
            }
        if any(w in message_lower for w in ["kya kar sakta", "kya kar sakte", "what can you do", "tumhara kaam", "your capability"]):
            return {
                "text": self._get_response(lang,
                    "I can help you with:\n\n- **Programming**: Code writing, debugging, explanations\n- **Tasks**: Create, build, deploy projects\n- **Questions**: Answer technical queries\n- **Memory**: Remember past conversations\n\nJust tell me what you need!",
                    "Main ye sab kar sakta hoon:\n\n- **Programming**: Code likhna, debug karna, samjhana\n- **Tasks**: Projects banana, deploy karna\n- **Sawaalon ke jawab**: Technical questions ka jawab\n- **Memory**: Past conversations yaad rakhna\n\nBatao kya chahiye!",
                    "Main ye sab help kar sakta hoon:\n\n- **Programming**: Code, debugging, explanations\n- **Tasks**: Projects banana\n- **Questions**: Jawab dena\n- **Memory**: Yaad rakhna\n\nBatao kya chahiye!",
                ),
                "type": "capabilities",
            }
        if any(w in message_lower for w in ["theek hai", "accha", "ok", "okay", "acha", "alright", "fine"]):
            return {
                "text": self._get_response(lang,
                    "Great! Let me know when you need anything else.",
                    "Theek hai! Jab kuch chahiye toh batao.",
                    "Accha! Jab kuch chahiye toh bolo.",
                ),
                "type": "acknowledgment",
            }
        return {
            "text": self._get_response(lang,
                "Interesting! Tell me more about that. I'm here to listen and help.",
                "Accha! Aur batao. Main sun raha hoon aur help karunga.",
                "Interesting hai! Aur batao, main help karunga.",
            ),
            "type": "casual_engagement",
        }

    def _handle_feedback_positive(self, user_id: str, message: str, intent: IntentResult, context: ContextState) -> Dict:
        lang = self._detect_language(message)
        self.context_engine.state.pending_action = None
        return {
            "text": self._get_response(lang,
                "Glad I could help! Is there anything else you'd like to work on?",
                "Accha laga help karke! Aur kuch karna hai?",
                "Nice! Aur kuch chahiye toh batao.",
            ),
            "type": "feedback_ack",
        }

    def _handle_feedback_negative(self, user_id: str, message: str, intent: IntentResult, context: ContextState) -> Dict:
        lang = self._detect_language(message)
        pending = self.context_engine.state.pending_action
        if pending == "correction_pending":
            return {
                "text": self._get_response(lang,
                    "I'm sorry that didn't work. Could you tell me what went wrong? I want to get it right.",
                    "Maaf karo, galat ho gaya. Batao kya galat tha? Sahi karna chahta hoon.",
                    "Sorry yaar, gadbad ho gayi. Batao kya problem thi?",
                ),
                "type": "correction_request",
            }
        return {
            "text": self._get_response(lang,
                "I apologize. Let me try again. Can you describe the issue in more detail?",
                "Maaf karo. Dobara try karta hoon. Problem detail mein batao.",
                "Sorry! Ek baar aur try karte hain. Issue batao detail mein.",
            ),
            "type": "retry_request",
        }

    def _handle_command(self, user_id: str, message: str, intent: IntentResult, context: ContextState) -> Dict:
        lang = self._detect_language(message)
        message_lower = message.lower()
        if any(w in message_lower for w in ["stop", "ruk", "cancel", "radd", "band"]):
            self.context_engine.state.pending_action = None
            return {
                "text": self._get_response(lang,
                    "Got it, I've stopped that. What would you like to do instead?",
                    "Ruk gaya. Ab kya karna hai?",
                    "Theek hai, band kar diya. Ab kya karun?",
                ),
                "type": "command_ack",
            }
        if any(w in message_lower for w in ["clear", "saaf", "reset"]):
            self.context_engine.clear_context()
            return {
                "text": self._get_response(lang,
                    "Context cleared! Starting fresh. How can I help you?",
                    "Sab saaf! Fresh start. Kya karna hai?",
                    "Clear ho gaya! Naya start. Batao kya karna hai?",
                ),
                "type": "command_ack",
            }
        if any(w in message_lower for w in ["save", "bachao", "store"]):
            return {
                "text": self._get_response(lang,
                    "I've noted that. Is there anything specific you'd like me to save to memory?",
                    "Note kar liya. Kuch specific save karna hai memory mein?",
                    "Yaad kar liya. Kuch specific save karna hai?",
                ),
                "type": "command_ack",
            }
        return {
            "text": self._get_response(lang,
                "Command received. What would you like me to do?",
                "Command mila. Kya karna hai?",
                "Samajh gaya. Kya karun?",
            ),
            "type": "command_ack",
        }

    def _handle_reflection(self, user_id: str, message: str, intent: IntentResult, context: ContextState) -> Dict:
        lang = self._detect_language(message)
        message_lower = message.lower()
        if any(w in message_lower for w in ["past", "previous", "history", "yaad"]):
            recent = self.memory_engine.get_recent_memories(5)
            user_memories = [m for m in recent if m.get("metadata", {}).get("user_id") == user_id]
            if user_memories:
                history_text = "\n".join(
                    [f"- {m['content'][:100]}" for m in user_memories[:3]]
                )
                return {
                    "text": self._get_response(lang,
                        f"Here's what I remember from our recent conversation:\n\n{history_text}\n\nWant to discuss any of these?",
                        f"Ye hai hamari recent conversation:\n\n{history_text}\n\nInme se kisi ke baare mein baat karna hai?",
                        f"Recent conversation yaad hai:\n\n{history_text}\n\nKisi ke baare mein baat karein?",
                    ),
                    "type": "reflection_history",
                }
            return {
                "text": self._get_response(lang,
                    "I don't have much history with you yet, but I'm building my memory with each conversation. What would you like to reflect on?",
                    "Abhi zyada history nahi hai, lekin har conversation se seekh raha hoon. Kya soch rahe ho?",
                    "Abhi zyada history nahi hai, seekh raha hoon. Kya baat karni hai?",
                ),
                "type": "reflection_fresh",
            }
        if any(w in message_lower for w in ["learn", "seekho", "improve"]):
            return {
                "text": self._get_response(lang,
                    "I believe in continuous improvement! Every conversation helps me learn. What would you like to explore or improve together?",
                    "Main continuous improvement mein believe karta hoon! Har conversation se seekhta hoon. Kya explore karna hai?",
                    "Improve karna hai? Har conversation se seekhta hoon. Kya karna hai?",
                ),
                "type": "reflection_growth",
            }
        return {
            "text": self._get_response(lang,
                "I appreciate your reflective approach. Let's think together. What's on your mind?",
                "Aapka sochne ka tarika accha hai. Mil ke sochte hain. Kya dimaag mein hai?",
                "Accha sochte ho! Mil ke sochte hain. Kya baat hai?",
            ),
            "type": "reflection_open",
        }

    def _store_message(self, user_id: str, role: str, content: str, intent: Optional[IntentResult], context: ContextState):
        intent_str = intent.intent if intent else None
        entities_str = json.dumps(intent.entities) if intent else None
        context_snapshot = json.dumps({
            "topic": context.current_topic,
            "mode": context.conversation_mode,
            "entities": context.entities,
        })
        self.db.execute(
            """INSERT INTO conversation_log (user_id, role, content, intent, entities, context_snapshot, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, role, content, intent_str, entities_str, context_snapshot, time.time()),
        )

    def _store_user_memory(self, user_id: str, message: str, intent: IntentResult):
        metadata = {
            "user_id": user_id,
            "intent": intent.intent,
            "entities": json.dumps(intent.entities),
            "topic": self.context_engine.state.current_topic,
        }
        self.memory_engine.store_memory(message, "SHORT_TERM", metadata)

    def _store_assistant_memory(self, user_id: str, response: str, intent: IntentResult):
        metadata = {
            "user_id": user_id,
            "role": "assistant",
            "intent": intent.intent,
            "topic": self.context_engine.state.current_topic,
        }
        if intent.intent in ["TASK_REQUEST", "QUESTION"]:
            self.memory_engine.store_memory(response, "LONG_TERM", metadata)
        else:
            self.memory_engine.store_memory(response, "SHORT_TERM", metadata)

    def get_conversation_history(self, user_id: str, limit: int = 20) -> List[Dict]:
        rows = self.db.fetch_all(
            """SELECT role, content, intent, timestamp
               FROM conversation_log
               WHERE user_id = ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (user_id, limit),
        )
        if not rows:
            return []
        history = []
        for row in reversed(rows):
            history.append({
                "role": row[0],
                "content": row[1],
                "intent": row[2],
                "timestamp": row[3],
            })
        return history

    def get_user_stats(self, user_id: str) -> Dict:
        total = self.db.fetch_one(
            "SELECT COUNT(*) FROM conversation_log WHERE user_id = ?",
            (user_id,),
        )
        intents = self.db.fetch_all(
            "SELECT intent, COUNT(*) as cnt FROM conversation_log WHERE user_id = ? AND intent IS NOT NULL GROUP BY intent ORDER BY cnt DESC",
            (user_id,),
        )
        first = self.db.fetch_one(
            "SELECT MIN(timestamp) FROM conversation_log WHERE user_id = ?",
            (user_id,),
        )
        last = self.db.fetch_one(
            "SELECT MAX(timestamp) FROM conversation_log WHERE user_id = ?",
            (user_id,),
        )
        return {
            "total_messages": total[0] if total else 0,
            "intent_distribution": {row[0]: row[1] for row in intents} if intents else {},
            "first_conversation": first[0] if first else None,
            "last_conversation": last[0] if last else None,
        }

    def prune_old_conversations(self, user_id: Optional[str] = None, older_than_days: int = 90) -> int:
        cutoff = time.time() - (older_than_days * 86400)
        if user_id:
            self.db.execute(
                "DELETE FROM conversation_log WHERE user_id = ? AND timestamp < ?",
                (user_id, cutoff),
            )
        else:
            self.db.execute(
                "DELETE FROM conversation_log WHERE timestamp < ?",
                (cutoff,),
            )
        return 0
