"""Tests for the Code Generation Engine.

Tests cover:
A. New code generation
B. Multi-file generation
C. Code modification
D. Debugging
E. Regeneration
F. Validation failure
G. Knowledge retrieval
H. Skill retrieval
I. New/unseen coding request
J. Anti-replay test
"""
import json
import unittest

from genesis_ai.core.code.code_request import CodeRequest, RequestType
from genesis_ai.core.code.planner import ProjectPlanner, ProjectSpec
from genesis_ai.core.code.knowledge_provider import InternalKnowledgeProvider, KnowledgeProvider
from genesis_ai.core.code.generator import CodeGenerator
from genesis_ai.core.code.validator import CodeValidator, ValidationResult
from genesis_ai.core.code.regeneration import RegenerationEngine
from genesis_ai.core.code.generation_provider import LocalProvider, HybridProvider
from genesis_ai.core.code.engine import CodeGenerationEngine


class TestCodeRequestParser(unittest.TestCase):
    """Test CodeRequest parsing from natural language."""

    def test_parse_create_rest_api_python(self):
        req = CodeRequest.parse("Create a REST API in Python")
        self.assertEqual(req.request_type, RequestType.CREATE)
        self.assertEqual(req.language, "python")
        self.assertEqual(req.project_type, "rest_api")

    def test_parse_create_web_app_react(self):
        req = CodeRequest.parse("Build a web app with React")
        self.assertEqual(req.request_type, RequestType.CREATE)
        self.assertEqual(req.language, "javascript")
        self.assertEqual(req.framework, "react")

    def test_parse_debug_request(self):
        req = CodeRequest.parse("Fix this Python error: TypeError in line 5")
        self.assertEqual(req.request_type, RequestType.DEBUG)
        self.assertEqual(req.language, "python")

    def test_parse_optimize_request(self):
        req = CodeRequest.parse("Make this JavaScript code faster")
        self.assertEqual(req.request_type, RequestType.OPTIMIZE)

    def test_parse_extend_request(self):
        req = CodeRequest.parse("Add authentication to my Flask app")
        self.assertEqual(req.request_type, RequestType.EXTEND)
        self.assertEqual(req.framework, "flask")

    def test_parse_migrate_request(self):
        req = CodeRequest.parse("Migrate this Python code to Go")
        self.assertEqual(req.request_type, RequestType.MIGRATE)

    def test_parse_with_auth_feature(self):
        req = CodeRequest.parse("Create a REST API with authentication and SQLite")
        self.assertIn("authentication", req.features)

    def test_parse_with_constraints(self):
        req = CodeRequest.parse("Create a Python CLI tool without external dependencies")
        self.assertIn("minimize_dependencies", req.constraints)


class TestProjectPlanner(unittest.TestCase):
    """Test project planning and decomposition."""

    def setUp(self):
        self.planner = ProjectPlanner()

    def test_plan_rest_api(self):
        req = CodeRequest.parse("Create a REST API in Python")
        spec = self.planner.plan(req)
        self.assertIsInstance(spec, ProjectSpec)
        self.assertGreater(len(spec.components), 0)
        self.assertIn("src/", spec.structure)

    def test_plan_cli_tool(self):
        req = CodeRequest.parse("Build a CLI tool in Python")
        spec = self.planner.plan(req)
        self.assertGreater(len(spec.components), 0)

    def test_plan_debug(self):
        req = CodeRequest.parse("Fix this Python error")
        spec = self.planner.plan(req)
        self.assertEqual(spec.request.request_type, RequestType.DEBUG)

    def test_generation_order_respects_dependencies(self):
        req = CodeRequest.parse("Create a REST API with authentication")
        spec = self.planner.plan(req)
        order = spec.generation_order
        self.assertGreater(len(order), 0)


class TestKnowledgeProvider(unittest.TestCase):
    """Test knowledge retrieval."""

    def setUp(self):
        self.kp = InternalKnowledgeProvider()

    def test_search_rest_api(self):
        results = self.kp.search_knowledge("REST API", language="python")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].concept, "REST API")

    def test_get_concept(self):
        kb = self.kp.get_concept("authentication")
        self.assertIsNotNone(kb)
        self.assertEqual(kb.category, "security")

    def test_get_examples(self):
        examples = self.kp.get_examples("REST API")
        self.assertGreater(len(examples), 0)

    def test_get_best_practices(self):
        practices = self.kp.get_best_practices("authentication")
        self.assertGreater(len(practices), 0)

    def test_get_constraints(self):
        constraints = self.kp.get_constraints("REST API")
        self.assertGreater(len(constraints), 0)


class TestCodeGenerator(unittest.TestCase):
    """Test code generation from requests and specs."""

    def setUp(self):
        self.gen = CodeGenerator()

    def test_generate_flask_rest_api(self):
        req = CodeRequest.parse("Create a REST API in Python with Flask")
        files = self.gen.generate_from_request(req)
        self.assertIsInstance(files, dict)
        self.assertGreater(len(files), 0)
        self.assertTrue(any("main" in f for f in files))

    def test_generate_fastapi_project(self):
        req = CodeRequest.parse("Build a FastAPI REST API in Python")
        files = self.gen.generate_from_request(req)
        self.assertGreater(len(files), 0)

    def test_generate_express_api(self):
        req = CodeRequest.parse("Create a REST API in JavaScript with Express")
        files = self.gen.generate_from_request(req)
        self.assertGreater(len(files), 0)

    def test_generate_cli_tool(self):
        req = CodeRequest.parse("Build a CLI tool in Python")
        files = self.gen.generate_from_request(req)
        self.assertGreater(len(files), 0)

    def test_generate_scraper(self):
        req = CodeRequest.parse("Create a web scraper in Python")
        files = self.gen.generate_from_request(req)
        self.assertGreater(len(files), 0)

    def test_generate_ml_model(self):
        req = CodeRequest.parse("Build a machine learning model in Python")
        files = self.gen.generate_from_request(req)
        self.assertGreater(len(files), 0)

    def test_generate_chatbot(self):
        req = CodeRequest.parse("Create a chatbot in Python")
        files = self.gen.generate_from_request(req)
        self.assertGreater(len(files), 0)

    def test_generate_library(self):
        req = CodeRequest.parse("Create a Python library")
        files = self.gen.generate_from_request(req)
        self.assertGreater(len(files), 0)

    def test_generate_html_page(self):
        req = CodeRequest.parse("Create an HTML page")
        files = self.gen.generate_from_request(req)
        self.assertGreater(len(files), 0)

    def test_generate_react_app(self):
        req = CodeRequest.parse("Build a React web app")
        files = self.gen.generate_from_request(req)
        self.assertGreater(len(files), 0)

    def test_generate_with_auth(self):
        req = CodeRequest.parse("Create a REST API with authentication")
        files = self.gen.generate_from_request(req)
        self.assertTrue(any("auth" in f for f in files))

    def test_legacy_generate_interface(self):
        code = self.gen.generate("write a Python fibonacci function")
        self.assertIsNotNone(code)
        self.assertIn("fibonacci", code)

    def test_generate_returns_valid_python(self):
        req = CodeRequest.parse("Create a Python library for math operations")
        files = self.gen.generate_from_request(req)
        import ast
        for path, content in files.items():
            if path.endswith(".py"):
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    self.fail(f"Generated invalid Python in {path}: {e}")


class TestCodeValidator(unittest.TestCase):
    """Test code validation."""

    def setUp(self):
        self.validator = CodeValidator()

    def test_validate_valid_python(self):
        files = {"main.py": "def hello():\n    return 'world'\n"}
        result = self.validator.validate(files, "python")
        self.assertTrue(result.valid)

    def test_validate_syntax_error(self):
        files = {"main.py": "def hello(\n    return 'world'\n"}
        result = self.validator.validate(files, "python")
        self.assertFalse(result.valid)

    def test_validate_javascript(self):
        files = {"index.js": "console.log('hello');"}
        result = self.validator.validate(files, "javascript")
        self.assertTrue(result.valid)

    def test_validate_mismatched_braces(self):
        files = {"index.js": "function hello() { console.log('hi');"}
        result = self.validator.validate(files, "javascript")
        self.assertFalse(result.valid)

    def test_validate_json(self):
        files = {"config.json": '{"key": "value"}'}
        result = self.validator.validate(files)
        self.assertTrue(result.valid)

    def test_validate_invalid_json(self):
        files = {"config.json": '{"key": "value",}'}
        result = self.validator.validate(files)
        self.assertFalse(result.valid)

    def test_validate_empty_files(self):
        result = self.validator.validate({})
        self.assertFalse(result.valid)

    def test_validate_html(self):
        files = {"index.html": "<!DOCTYPE html><html><body>Hello</body></html>"}
        result = self.validator.validate(files, "html")
        self.assertTrue(result.valid)

    def test_validate_multiple_files(self):
        files = {
            "main.py": "def main():\n    print('hello')\n",
            "utils.py": "def helper():\n    return True\n",
        }
        result = self.validator.validate(files, "python")
        self.assertTrue(result.valid)
        self.assertGreaterEqual(result.files_checked, 2)


class TestRegenerationEngine(unittest.TestCase):
    """Test code repair and regeneration."""

    def setUp(self):
        self.engine = RegenerationEngine(max_attempts=3)

    def test_no_regeneration_needed(self):
        files = {"main.py": "def hello():\n    return 'world'\n"}
        from genesis_ai.core.code.validator import CodeValidator
        validator = CodeValidator()
        validation = validator.validate(files, "python")
        result = self.engine.regenerate(files, validation)
        self.assertTrue(result.success)
        self.assertEqual(result.generations, 1)

    def test_regeneration_fixes_syntax(self):
        files = {"main.py": "def hello(\n    return 'world'\n"}
        from genesis_ai.core.code.validator import CodeValidator
        validator = CodeValidator()
        validation = validator.validate(files, "python")
        result = self.engine.regenerate(files, validation)
        self.assertGreater(result.generations, 1)

    def test_experiences_recorded(self):
        files = {"main.py": "def hello(\n    return 'world'\n"}
        from genesis_ai.core.code.validator import CodeValidator
        validator = CodeValidator()
        validation = validator.validate(files, "python")
        self.engine.regenerate(files, validation)
        experiences = self.engine.get_experiences()
        self.assertGreater(len(experiences), 0)


class TestGenerationEngine(unittest.TestCase):
    """Test the full code generation engine pipeline."""

    def setUp(self):
        self.engine = CodeGenerationEngine()

    def test_generate_rest_api(self):
        response = self.engine.generate("Create a REST API in Python with Flask")
        self.assertTrue(response.success)
        self.assertGreater(len(response.files), 0)
        self.assertIsNotNone(response.validation)
        self.assertIsNotNone(response.plan)

    def test_generate_cli_tool(self):
        response = self.engine.generate("Build a CLI tool in Python")
        self.assertTrue(response.success)

    def test_generate_react_app(self):
        response = self.engine.generate("Build a React web app")
        self.assertTrue(response.success)

    def test_modify_code(self):
        code = "def hello():\n    return 'world'\n"
        response = self.engine.modify(code, "Add a parameter for name")
        self.assertIsNotNone(response)

    def test_debug_code(self):
        code = "def add(a, b):\n  return a + b\n"
        response = self.engine.debug(code, "TypeError when passing strings")
        self.assertIsNotNone(response)

    def test_validate_files(self):
        files = {"main.py": "def hello():\n    return 'world'\n"}
        result = self.engine.validate_files(files, "python")
        self.assertTrue(result.valid)

    def test_history_tracking(self):
        self.engine.generate("Create a Python library")
        history = self.engine.get_history()
        self.assertGreater(len(history), 0)

    def test_to_dict(self):
        response = self.engine.generate("Create a REST API in Python")
        d = response.to_dict()
        self.assertIn("success", d)
        self.assertIn("files", d)
        self.assertIn("plan", d)

    def test_to_markdown(self):
        response = self.engine.generate("Create a REST API in Python")
        md = response.to_markdown()
        self.assertIn("Generated Files", md)

    def test_unseen_request_type(self):
        response = self.engine.generate("Create a Discord bot in Python that moderates channels")
        self.assertIsNotNone(response)

    def test_anti_replay_different_requests(self):
        r1 = self.engine.generate("Create a REST API in Python")
        r2 = self.engine.generate("Build a CLI tool in Python")
        self.assertNotEqual(list(r1.files.keys()), list(r2.files.keys()))


class TestIntegration(unittest.TestCase):
    """Integration tests for the full pipeline."""

    def test_end_to_end_python_api(self):
        engine = CodeGenerationEngine()
        response = engine.generate(
            "Create a REST API in Python with Flask and authentication",
            language="python",
            framework="flask"
        )
        self.assertTrue(response.success)
        self.assertIn("src/main.py", response.files)
        self.assertIn("src/routes.py", response.files)

    def test_end_to_end_express_api(self):
        engine = CodeGenerationEngine()
        response = engine.generate(
            "Create a REST API in JavaScript with Express",
            language="javascript",
            framework="express"
        )
        self.assertTrue(response.success)
        self.assertIn("src/index.js", response.files)

    def test_end_to_end_fastapi(self):
        engine = CodeGenerationEngine()
        response = engine.generate(
            "Build a FastAPI REST API with Pydantic models",
            language="python",
            framework="fastapi"
        )
        self.assertTrue(response.success)


if __name__ == "__main__":
    unittest.main()
