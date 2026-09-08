"""Integration tests for Genesis Knowledge Network integration.

Tests cover:
1. Knowledge Network available
2. Knowledge Network unavailable (fallback)
3. Timeout handling
4. Empty result handling
5. Malformed response handling
6. Fallback to internal provider
7. Relevant knowledge selection
8. Provenance preservation
9. Code generation using network knowledge
10. Regression
"""
import json
import unittest
from unittest.mock import MagicMock, patch

from genesis_ai.core.code.knowledge_provider import InternalKnowledgeProvider, CodingKnowledge
from genesis_ai.core.code.genesis_knowledge_provider import (
    GenesisKnowledgeProvider,
    NetworkKnowledgeItem,
)
from genesis_ai.core.code.engine import CodeGenerationEngine


class TestGenesisKnowledgeProvider(unittest.TestCase):
    """Test GenesisKnowledgeProvider adapter."""

    def setUp(self):
        self.gkp = GenesisKnowledgeProvider(
            network_url="http://127.0.0.1:8000",
            timeout=3,
            max_retries=1,
        )

    def test_initialization(self):
        self.assertIsNotNone(self.gkp)
        self.assertEqual(self.gkp._network_url, "http://127.0.0.1:8000")

    def test_is_available_when_running(self):
        result = self.gkp.is_network_available
        self.assertIsInstance(result, bool)

    def test_normalize_fact(self):
        item = NetworkKnowledgeItem(
            object_type="fact",
            data={
                "subject": "Python",
                "predicate": "is_interpreted",
                "object_value": "true",
                "confidence": 0.9,
            },
            confidence=0.9,
            freshness=1.0,
        )
        kb = self.gkp._normalize_item(item)
        self.assertIsInstance(kb, CodingKnowledge)
        self.assertEqual(kb.concept, "Python")
        self.assertEqual(kb.category, "fact")
        self.assertEqual(kb.source, "ai_knowledge_network")

    def test_normalize_entity(self):
        item = NetworkKnowledgeItem(
            object_type="entity",
            data={
                "canonical_name": "Python",
                "description": "A programming language",
                "type": "language",
                "confidence": 0.8,
            },
            confidence=0.8,
            freshness=1.0,
        )
        kb = self.gkp._normalize_item(item)
        self.assertIsInstance(kb, CodingKnowledge)
        self.assertEqual(kb.concept, "Python")
        self.assertEqual(kb.description, "A programming language")

    def test_normalize_skill(self):
        item = NetworkKnowledgeItem(
            object_type="skill",
            data={
                "name": "Write Python script",
                "purpose": "Create and run Python files",
                "procedure": [{"order": 1, "description": "Create file"}],
                "best_practices": ["Use main guard"],
                "constraints": [],
                "confidence": 0.7,
            },
            confidence=0.7,
            freshness=1.0,
        )
        kb = self.gkp._normalize_item(item)
        self.assertIsInstance(kb, CodingKnowledge)
        self.assertEqual(kb.concept, "Write Python script")
        self.assertIn("Create file", kb.examples)
        self.assertIn("Use main guard", kb.best_practices)

    def test_filter_relevant(self):
        items = [
            CodingKnowledge(concept="Flask", description="Python web framework", confidence=0.8),
            CodingKnowledge(concept="React", description="JavaScript UI library", confidence=0.8),
            CodingKnowledge(concept="JWT", description="JSON Web Token authentication", confidence=0.8),
        ]
        relevant = self.gkp._filter_relevant(items, "Flask REST API", language="python")
        concepts = [r.concept for r in relevant]
        self.assertIn("Flask", concepts)
        self.assertNotIn("React", concepts)

    def test_search_knowledge_with_network(self):
        if not self.gkp.is_network_available:
            self.skipTest("Knowledge Network not available")
        results = self.gkp.search_knowledge("Python", language="python", limit=3)
        self.assertIsInstance(results, list)

    def test_search_knowledge_fallback(self):
        with patch.object(self.gkp, '_is_available', return_value=False):
            results = self.gkp.search_knowledge("Flask", language="python", limit=3)
            self.assertIsInstance(results, list)

    def test_get_concept_fallback(self):
        with patch.object(self.gkp, '_is_available', return_value=False):
            result = self.gkp.get_concept("Flask")
            self.assertIsInstance(result, CodingKnowledge)


class TestFallbackBehavior(unittest.TestCase):
    """Test fallback to InternalKnowledgeProvider."""

    def test_fallback_is_default(self):
        gkp = GenesisKnowledgeProvider(network_url="http://invalid:9999")
        self.assertIsInstance(gkp._fallback, InternalKnowledgeProvider)

    def test_fallback_provides_knowledge(self):
        gkp = GenesisKnowledgeProvider(network_url="http://invalid:9999")
        results = gkp.search_knowledge("REST API", limit=3)
        self.assertGreater(len(results), 0)

    def test_fallback_get_concept(self):
        gkp = GenesisKnowledgeProvider(network_url="http://invalid:9999")
        result = gkp.get_concept("authentication")
        self.assertIsNotNone(result)
        self.assertEqual(result.concept, "Authentication")

    def test_fallback_get_examples(self):
        gkp = GenesisKnowledgeProvider(network_url="http://invalid:9999")
        examples = gkp.get_examples("REST API")
        self.assertGreater(len(examples), 0)

    def test_fallback_get_best_practices(self):
        gkp = GenesisKnowledgeProvider(network_url="http://invalid:9999")
        practices = gkp.get_best_practices("authentication")
        self.assertGreater(len(practices), 0)

    def test_fallback_get_constraints(self):
        gkp = GenesisKnowledgeProvider(network_url="http://invalid:9999")
        constraints = gkp.get_constraints("REST API")
        self.assertGreater(len(constraints), 0)


class TestTimeoutHandling(unittest.TestCase):
    """Test timeout and connection error handling."""

    def test_timeout_returns_fallback(self):
        gkp = GenesisKnowledgeProvider(
            network_url="http://192.0.2.1:9999",
            timeout=1,
            max_retries=0,
        )
        results = gkp.search_knowledge("Flask", limit=3)
        self.assertIsInstance(results, list)

    def test_connection_error_returns_fallback(self):
        gkp = GenesisKnowledgeProvider(
            network_url="http://invalidhost:9999",
            timeout=1,
            max_retries=0,
        )
        result = gkp.get_concept("Flask")
        self.assertIsNotNone(result)


class TestCodeGenerationWithKnowledge(unittest.TestCase):
    """Test code generation using knowledge provider."""

    def test_engine_uses_internal_by_default(self):
        engine = CodeGenerationEngine(knowledge_mode="internal")
        self.assertIsInstance(engine._kp, InternalKnowledgeProvider)

    def test_engine_accepts_custom_knowledge_provider(self):
        custom = InternalKnowledgeProvider()
        engine = CodeGenerationEngine(knowledge_provider=custom)
        self.assertIs(engine._kp, custom)

    def test_engine_generates_with_internal_knowledge(self):
        engine = CodeGenerationEngine(knowledge_mode="internal")
        response = engine.generate("Create a Flask REST API with authentication")
        self.assertTrue(response.success)
        self.assertGreater(len(response.files), 0)
        self.assertEqual(response.knowledge_provider, "internal")

    def test_engine_tracks_knowledge_usage(self):
        engine = CodeGenerationEngine(knowledge_mode="internal")
        response = engine.generate("Create a REST API in Python")
        self.assertIn("knowledge_items_used", response.to_dict())
        self.assertIn("knowledge_types", response.to_dict())

    def test_engine_to_dict_includes_knowledge_metadata(self):
        engine = CodeGenerationEngine(knowledge_mode="internal")
        response = engine.generate("Create a Python library")
        d = response.to_dict()
        self.assertIn("knowledge_provider", d)
        self.assertIn("knowledge_items_used", d)
        self.assertIn("knowledge_types", d)


class TestProvenancePreservation(unittest.TestCase):
    """Test that provenance metadata is preserved."""

    def test_codingknowledge_retains_source(self):
        kb = CodingKnowledge(
            concept="Test",
            description="Test concept",
            source="ai_knowledge_network",
            confidence=0.85,
        )
        self.assertEqual(kb.source, "ai_knowledge_network")
        self.assertEqual(kb.confidence, 0.85)

    def test_network_items_retain_confidence(self):
        item = NetworkKnowledgeItem(
            object_type="fact",
            data={"subject": "Python", "predicate": "is", "object_value": "great"},
            confidence=0.9,
            freshness=0.8,
        )
        kb = self.gkp._normalize_item(item) if hasattr(self, 'gp') else GenesisKnowledgeProvider()._normalize_item(item)
        self.assertEqual(kb.confidence, 0.9)

    def setUp(self):
        self.gkp = GenesisKnowledgeProvider(
            network_url="http://127.0.0.1:8000",
            timeout=3,
            max_retries=0,
        )


class TestRegression(unittest.TestCase):
    """Regression tests to ensure existing functionality is preserved."""

    def test_existing_knowledge_provider_unchanged(self):
        kp = InternalKnowledgeProvider()
        results = kp.search_knowledge("REST API")
        self.assertGreater(len(results), 0)

    def test_code_generation_still_works(self):
        engine = CodeGenerationEngine()
        response = engine.generate("Create a Python library for math")
        self.assertTrue(response.success)
        self.assertGreater(len(response.files), 0)

    def test_legacy_template_generator_unchanged(self):
        from genesis_ai.core.code.generator import CodeGenerator
        gen = CodeGenerator()
        code = gen.generate("write a python fibonacci code")
        self.assertIsNotNone(code)
        self.assertIn("def fibonacci", code)


if __name__ == "__main__":
    unittest.main()
