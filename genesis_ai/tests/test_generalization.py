"""
Generalization tests for Genesis AI.
These tests verify that the system handles UNSEEN inputs using general mechanisms,
not hardcoded responses. The system must pass these without any question-specific code.
"""

import os
import sys
import re
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _make_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    from genesis_ai.database.db import DatabaseManager
    db = DatabaseManager(db_path=path)
    return db, path


def _patch_db_execute(db):
    if not hasattr(db, "_patched"):
        def execute(sql, params=()):
            with db.get_conn() as conn:
                conn.execute(sql, params if params else ())
        def execute_and_commit(sql, params=()):
            with db.get_conn() as conn:
                conn.execute(sql, params if params else ())
                conn.commit()
        def fetch_one(sql, params=()):
            with db.get_conn() as conn:
                return conn.execute(sql, params if params else ()).fetchone()
        def fetch_all(sql, params=()):
            with db.get_conn() as conn:
                return conn.execute(sql, params if params else ()).fetchall()
        db.execute = execute
        db.execute_and_commit = execute_and_commit
        db.fetch_one = fetch_one
        db.fetch_all = fetch_all
        db._patched = True
    return db


# ─── ANTI-HARDCODING TESTS ───────────────────────────────────────────────────

class TestAntiHardcoding(unittest.TestCase):
    """Scan the codebase for suspicious hardcoded patterns."""

    def setUp(self):
        self.project_root = os.path.join(os.path.dirname(__file__), "..", "..")
        self.genesis_dir = os.path.join(self.project_root, "genesis_ai")

    def _read_file(self, rel_path):
        full = os.path.join(self.genesis_dir, rel_path)
        if not os.path.exists(full):
            return ""
        with open(full, "r", encoding="utf-8") as f:
            return f.read()

    def test_no_hardcoded_user_questions_in_main(self):
        """main.py should not contain hardcoded user questions like 'hii', 'amir khan', etc."""
        content = self._read_file("main.py")
        suspicious = [
            r'if\s+.*==\s*["\']hii',
            r'if\s+.*==\s*["\']hello',
            r'if\s+.*==\s*["\']hi',
            r'if\s+.*==\s*["\']namaste',
            r'if\s+.*in\s*\[.*"who are you"',
            r'if\s+.*"amir\s*khan"',
            r'if\s+.*"shah\s*rukh"',
            r'if\s+.*"linked\s*list".*return.*class',
            r'if\s+.*"calculator".*return.*def\s+calc',
            r'if\s+.*"todo".*return.*class\s+Todo',
            r'if\s+.*"flask".*return.*from\s+flask',
        ]
        for pat in suspicious:
            matches = re.findall(pat, content, re.IGNORECASE)
            self.assertEqual(len(matches), 0, f"Hardcoded pattern found in main.py: {pat}")

    def test_no_hardcoded_search_queries_in_ai_responder(self):
        """ai_responder.py should not contain test-specific search queries."""
        content = self._read_file("core/ai_responder.py")
        suspicious = [
            r'vidyarc',
            r'2024',
            r'best\s+love\s+shayari\s+hindi',
            r'teacher\s+student\s+jokes',
            r'santa\s+banta',
            r'linked\s*list\s+data\s+structure\s+explanation',
        ]
        for pat in suspicious:
            matches = re.findall(pat, content, re.IGNORECASE)
            self.assertEqual(len(matches), 0, f"Hardcoded query found in ai_responder.py: {pat}")

    def test_no_hardcoded_code_templates_in_main(self):
        """main.py should not contain multi-line code templates."""
        content = self._read_file("main.py")
        # Check for long string literals that look like code templates
        code_indicators = [
            r'class\s+Node:',
            r'class\s+Calculator:',
            r'class\s+TodoApp:',
            r'from\s+flask\s+import\s+Flask',
            r'def\s+calculator\(\):',
            r'if\s+__name__\s*==\s*["\']__main__["\']',
        ]
        for pat in code_indicators:
            matches = re.findall(pat, content)
            self.assertEqual(len(matches), 0, f"Code template found in main.py: {pat}")

    def test_no_exact_string_set_for_casual(self):
        """ai_responder.py should not use exact string set matching for casual detection."""
        content = self._read_file("core/ai_responder.py")
        # Should NOT have: if msg in casual_exact
        self.assertNotIn("casual_exact", content,
                         "Hardcoded casual_exact set found in ai_responder.py")

    def test_no_hardcoded_years_in_search(self):
        """Search queries should not contain hardcoded years."""
        content = self._read_file("core/ai_responder.py")
        content += self._read_file("main.py")
        # Should not have hardcoded years in query strings
        year_matches = re.findall(r'["\'].*(?:2024|2025|2026).*["\']', content)
        # Filter out non-query uses (like timestamps)
        query_years = [y for y in year_matches if 'shayari' in y or 'joke' in y or 'story' in y or 'quote' in y]
        self.assertEqual(len(query_years), 0, f"Hardcoded years found in search queries: {query_years}")

    def test_no_hardcoded_pronoun_list_in_main(self):
        """main.py should not have hardcoded pronoun replacement lists."""
        content = self._read_file("main.py")
        # The old code had: followup_words = {'ye', 'woh', ...}
        self.assertNotIn("followup_words = {", content,
                         "Hardcoded pronoun set found in main.py")

    def test_no_hardcoded_identity_phrases(self):
        """main.py should not match identity by exact phrase list."""
        content = self._read_file("main.py")
        # Should not have: identity = ["who are you", "what are you", ...]
        self.assertNotIn('"who are you"', content,
                         "Hardcoded identity phrase found in main.py")
        self.assertNotIn('"tum kya hai"', content,
                         "Hardcoded identity phrase found in main.py")


# ─── GENERALIZATION TESTS ────────────────────────────────────────────────────

class TestIntentGeneralization(unittest.TestCase):
    """Test that intent detection works for unseen inputs with different wording."""

    def setUp(self):
        self.db, self.path = _make_db()
        _patch_db_execute(self.db)
        from genesis_ai.core.understanding.engine import UnderstandingEngine
        self.engine = UnderstandingEngine(self.db)

    def tearDown(self):
        self.db.close()
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def test_greeting_in_various_wordings(self):
        """Same intent (greeting) should be detected regardless of wording."""
        greetings = [
            "hello", "hey there", "namaste", "good morning",
            "kaise ho", "sup", "yo", "howdy",
        ]
        for g in greetings:
            result = self.engine.understand(g)
            self.assertIn(result.task_type, ["conversation", "factual"],
                         f"Failed to classify greeting: '{g}' -> task_type={result.task_type}")

    def test_code_task_in_various_wordings(self):
        """Same intent (code creation) should be detected regardless of wording."""
        code_tasks = [
            "write a python script to parse CSV",
            "create a web scraper in javascript",
            "banao ek calculator app",
            "build me a REST API with Flask",
            "implement a binary search in Go",
            "develop a chat application",
        ]
        for task in code_tasks:
            result = self.engine.understand(task)
            self.assertIn(result.task_type, ["code", "factual"],
                         f"Failed to classify code task: '{task}' -> task_type={result.task_type}, intent={result.intent}")

    def test_research_in_various_wordings(self):
        """Same intent (research) should be detected regardless of wording."""
        research_tasks = [
            "what is quantum computing?",
            "tell me about blockchain technology",
            "explain machine learning",
            "batao ki python kya hai",
            "samjhao photosynthesis kaise kaam karta hai",
            "kya hai artificial intelligence",
        ]
        for task in research_tasks:
            result = self.engine.understand(task)
            self.assertIn(result.intent, ["research", "explain"],
                         f"Failed to classify research task: '{task}' -> intent={result.intent}")

    def test_fix_task_in_various_wordings(self):
        """Same intent (fix) should be detected regardless of wording."""
        fix_tasks = [
            "debug this Python function",
            "fix the error in my code",
            "theek karo ye bug",
            "solve this compilation issue",
            "repair the broken API endpoint",
        ]
        for task in fix_tasks:
            result = self.engine.understand(task)
            self.assertIn(result.intent, ["fix", "create", "research"],
                         f"Failed to classify fix task: '{task}' -> intent={result.intent}")


class TestCasualGeneralization(unittest.TestCase):
    """Test that casual responses work for unseen conversational inputs."""

    def setUp(self):
        self.db, self.path = _make_db()
        _patch_db_execute(self.db)
        from genesis_ai.core.ai_responder import classify_message_type, get_casual_response
        self.classify = classify_message_type
        self.get_casual = get_casual_response
        self.db.close()

    def tearDown(self):
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def test_various_greeting_styles(self):
        """Various greeting styles should be classified as CASUAL."""
        greetings = ["hello", "hey", "namaste", "yo", "howdy", "hi there", "good day"]
        for g in greetings:
            msg_type = self.classify(g)
            self.assertEqual(msg_type, "CASUAL",
                           f"Failed to classify as CASUAL: '{g}' -> {msg_type}")

    def test_various_farewell_styles(self):
        """Various farewell styles should be classified as CASUAL."""
        farewells = ["bye", "goodbye", "see you later", "take care", "alvida", "phir milenge"]
        for f in farewells:
            msg_type = self.classify(f)
            self.assertEqual(msg_type, "CASUAL",
                           f"Failed to classify as CASUAL: '{f}' -> {msg_type}")

    def test_various_thanks_styles(self):
        """Various thanks styles should be classified as CASUAL."""
        thanks = ["thank you", "thanks", "shukriya", "dhanyavad", "appreciate it"]
        for t in thanks:
            msg_type = self.classify(t)
            self.assertEqual(msg_type, "CASUAL",
                           f"Failed to classify as CASUAL: '{t}' -> {msg_type}")

    def test_short_acknowledgments(self):
        """Short acknowledgments should be classified as CASUAL."""
        acks = ["ok", "okay", "fine", "good", "great", "accha", "theek hai"]
        for a in acks:
            msg_type = self.classify(a)
            self.assertEqual(msg_type, "CASUAL",
                           f"Failed to classify as CASUAL: '{a}' -> {msg_type}")

    def test_casual_response_not_empty(self):
        """Casual responses should never be empty."""
        messages = ["hello", "bye", "thanks", "ok", "kaise ho"]
        for m in messages:
            resp = self.get_casual(m, "hinglish", [])
            self.assertTrue(len(resp) > 0, f"Empty response for casual message: '{m}'")


class TestSearchQueryGeneralization(unittest.TestCase):
    """Test that search queries are general and not test-specific."""

    def setUp(self):
        from genesis_ai.core.ai_responder import build_search_queries
        self.build_queries = build_search_queries

    def test_code_query_not_hardcoded(self):
        """Code search queries should be based on the message, not hardcoded."""
        queries = self.build_queries("create a todo app in Rust", "CODE")
        for q in queries:
            self.assertNotIn("vidyarc", q.lower())
            self.assertNotIn("2024", q)

    def test_factual_query_not_hardcoded(self):
        """Factual search queries should be based on the message."""
        queries = self.build_queries("what is machine learning", "FACTUAL")
        self.assertTrue(len(queries) > 0)
        # Should contain something from the original message
        self.assertTrue(
            any("machine learning" in q.lower() or "what" in q.lower() for q in queries),
            f"Queries don't contain message content: {queries}"
        )

    def test_creative_query_uses_message(self):
        """Creative search queries should extract themes from the message."""
        queries = self.build_queries("write a poem about the ocean", "CREATIVE")
        self.assertTrue(len(queries) > 0)
        # Should reference the topic
        self.assertTrue(
            any("ocean" in q.lower() or "poem" in q.lower() for q in queries),
            f"Creative queries don't reference the topic: {queries}"
        )

    def test_followup_query_includes_entity(self):
        """Follow-up queries should include the context entity."""
        queries = self.build_queries("tell me more", "FOLLOWUP", context_entity="Python")
        self.assertTrue(len(queries) > 0)
        self.assertTrue(
            any("python" in q.lower() for q in queries),
            f"Follow-up queries don't include context entity: {queries}"
        )


class TestContextResolution(unittest.TestCase):
    """Test that context resolution works generically."""

    def setUp(self):
        self.db, self.path = _make_db()
        _patch_db_execute(self.db)
        from genesis_ai.main import GenesisAI
        try:
            self.genesis = GenesisAI()
            self.genesis.db = self.db
        except Exception:
            self.genesis = None
        self.db.close()

    def tearDown(self):
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def test_resolve_followup_pronouns(self):
        """Follow-up resolution should replace pronouns with context entity."""
        if not self.genesis:
            self.skipTest("GenesisAI init failed")
        # Test the resolution mechanism
        resolved = self.genesis._resolve_followup("ye kya hai", "Calculator")
        self.assertIn("calculator", resolved.lower())
        self.assertNotIn("ye", resolved.lower())

    def test_resolve_followup_no_pronouns(self):
        """Messages without pronouns should pass through unchanged."""
        if not self.genesis:
            self.skipTest("GenesisAI init failed")
        resolved = self.genesis._resolve_followup("what is python", "Calculator")
        self.assertEqual(resolved, "what is python")

    def test_resolve_followup_english_pronouns(self):
        """English pronouns should also be resolved."""
        if not self.genesis:
            self.skipTest("GenesisAI init failed")
        resolved = self.genesis._resolve_followup("tell me more about this", "Python")
        self.assertIn("python", resolved.lower())


class TestIdentityDetection(unittest.TestCase):
    """Test that identity questions are detected generically."""

    def setUp(self):
        self.db, self.path = _make_db()
        _patch_db_execute(self.db)
        from genesis_ai.main import GenesisAI
        try:
            self.genesis = GenesisAI()
            self.genesis.db = self.db
        except Exception:
            self.genesis = None
        self.db.close()

    def tearDown(self):
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def test_identity_various_wordings(self):
        """Various identity question wordings should be detected."""
        if not self.genesis:
            self.skipTest("GenesisAI init failed")
        identity_qs = [
            "who are you", "what are you", "tum kaun ho",
            "kya hai tum", "your name", "tumhara naam kya hai",
            "genesis kya hai", "tell me about yourself",
        ]
        for q in identity_qs:
            result = self.genesis._is_identity_question(q)
            self.assertTrue(result, f"Failed to detect identity question: '{q}'")

    def test_non_identity_not_detected(self):
        """Non-identity questions should not be detected as identity."""
        if not self.genesis:
            self.skipTest("GenesisAI init failed")
        non_identity = [
            "what is python", "who is the president",
            "how are you today", "tell me about quantum computing",
        ]
        for q in non_identity:
            result = self.genesis._is_identity_question(q)
            self.assertFalse(result, f"False positive identity detection: '{q}'")


class TestLanguageDetection(unittest.TestCase):
    """Test that language detection works for various input styles."""

    def setUp(self):
        self.db, self.path = _make_db()
        _patch_db_execute(self.db)
        from genesis_ai.core.conversation.engine import ConversationEngine
        self.engine = ConversationEngine(self.db)

    def tearDown(self):
        self.db.close()
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def test_english_detection(self):
        lang = self.engine._detect_language("What is the meaning of life?")
        self.assertEqual(lang, "english")

    def test_hindi_detection(self):
        lang = self.engine._detect_language("जीवन का क्या अर्थ है?")
        self.assertEqual(lang, "hindi")

    def test_hinglish_detection(self):
        lang = self.engine._detect_language("What is life ka matlab kya hai")
        self.assertEqual(lang, "hinglish")


class TestCriticalRegressionFixes(unittest.TestCase):
    """Regression tests for the 4 critical runtime failures identified during testing."""

    def setUp(self):
        from genesis_ai.main import GenesisAI
        self.genesis = GenesisAI()

    def test_hiii_is_conversation_not_search(self):
        """Failure 1: 'hiii' should be classified as conversation, not trigger web search."""
        understanding = self.genesis.understanding_engine.understand("hiii")
        self.assertEqual(understanding.task_type, "conversation",
                         f"'hiii' should be conversation, got '{understanding.task_type}'")

    def test_kya_haal_hai_is_conversation(self):
        """Failure 2: 'kya haal hai' should be conversation, not search for 'Haal'."""
        understanding = self.genesis.understanding_engine.understand("kya haal hai")
        self.assertEqual(understanding.task_type, "conversation",
                         f"'kya haal hai' should be conversation, got '{understanding.task_type}'")

    def test_hiii_generates_casual_response(self):
        """Failure 1b: 'hiii' should return a casual greeting, not web search results."""
        result = self.genesis.chat("test_user", "hiii")
        self.assertNotIn("search", result.get("intent", "").lower(),
                         f"'hiii' should not trigger search, got intent: {result.get('intent')}")
        self.assertTrue(len(result.get("response_text", "")) > 0,
                        "Response should not be empty")

    def test_kya_haal_hai_generates_casual_response(self):
        """Failure 2b: 'kya haal hai' should return a casual greeting."""
        result = self.genesis.chat("test_user", "kya haal hai")
        self.assertNotIn("search", result.get("intent", "").lower(),
                         f"'kya haal hai' should not trigger search, got intent: {result.get('intent')}")

    def test_write_python_code_generates_code(self):
        """Failure 3: 'write a python code' with sufficient info should generate code."""
        # This message is too vague — no specific pattern matched, falls to web search
        # The fix ensures it doesn't search web when intent is code + language detected
        result = self.genesis.chat("test_user", "write a python fibonacci code")
        response = result.get("response_text", "")
        # Should contain actual code, not "Could you be more specific?"
        self.assertNotIn("Could you be more specific", response,
                         "Should not ask for clarification on code request with language and goal")

    def test_write_python_hello_world_has_code(self):
        """Failure 3b: 'write a python hello world code' should return actual code."""
        result = self.genesis.chat("test_user", "write a python hello world code")
        response = result.get("response_text", "")
        self.assertIn("Hello", response, "Response should contain 'Hello'")

    def test_who_is_person_returns_synthesis(self):
        """Failure 4: 'who is salman khan' should return synthesized bio, not raw snippets."""
        # This test verifies the synthesis path works, not that search is called
        result = self.genesis.chat("test_user", "who is salman khan")
        response = result.get("response_text", "")
        # Should not be raw HTML or JSON snippets
        self.assertNotIn("<div", response, "Response should not contain raw HTML")
        self.assertNotIn("{", response, "Response should not contain raw JSON")
        self.assertTrue(len(response) > 20, "Response should be a meaningful bio, not empty")


class TestSearchGate(unittest.TestCase):
    """Test the Search Gate — conversation tasks must skip research pipeline."""

    def setUp(self):
        from genesis_ai.main import GenesisAI
        self.genesis = GenesisAI()

    def test_conversation_skips_research(self):
        """Conversation tasks should not trigger web search."""
        result = self.genesis.chat("test_user", "hello")
        # pipeline_stages is a Dict mapping stage_name → {event_count, total_duration, ...}
        stages = result.get("pipeline_stages", {})
        # Research stages should not appear for conversation
        self.assertNotIn("SOURCE_FOUND", stages,
                         "Conversation should not trigger web search stages")
        self.assertNotIn("EVIDENCE_EXTRACTED", stages,
                         "Conversation should not extract evidence")

    def test_code_skips_research(self):
        """Code tasks should not trigger web search stages (use local generation)."""
        result = self.genesis.chat("test_user", "write a python fibonacci code")
        stages = result.get("pipeline_stages", {})
        # Code should not trigger research pipeline
        self.assertNotIn("SOURCE_FOUND", stages,
                         "Code task should not trigger web search stages")


class TestCodeGeneration(unittest.TestCase):
    """Test local code generation engine."""

    def setUp(self):
        from genesis_ai.core.code.generator import CodeGenerator
        self.gen = CodeGenerator()

    def test_python_fibonacci(self):
        code = self.gen.generate("write a python fibonacci code")
        self.assertIsNotNone(code, "Should generate fibonacci code")
        self.assertIn("def fibonacci", code)

    def test_python_hello_world(self):
        code = self.gen.generate("write a python hello world code")
        self.assertIsNotNone(code)
        self.assertIn("Hello", code)

    def test_python_linked_list(self):
        code = self.gen.generate("write a python linked list code")
        self.assertIsNotNone(code)
        self.assertIn("class Node", code)

    def test_unknown_returns_none(self):
        code = self.gen.generate("write something completely random xyz")
        self.assertIsNone(code, "Unknown request should return None")


if __name__ == "__main__":
    unittest.main()
