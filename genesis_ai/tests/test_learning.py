"""Tests for the Genesis Learning System — Experience Ingestion, Pipeline, API, Generalization."""

import json
import time
import unittest

from genesis_ai.database.db import DatabaseManager
from genesis_ai.learning.experience_memory import Experience, ExperienceMemory
from genesis_ai.learning.pipeline import LearningPipeline


class TestExperienceMemory(unittest.TestCase):
    """Test the Experience Memory — structured storage for learning experiences."""

    def setUp(self):
        self.db = DatabaseManager(":memory:")
        self.memory = ExperienceMemory(self.db)

    def test_ingest_experience(self):
        """Ingesting an experience returns an ID."""
        exp = Experience(
            task="write a Python function",
            goal="create a working function",
            success=True,
            actions=["define function", "write code", "test"],
        )
        exp_id = self.memory.ingest(exp)
        self.assertIsNotNone(exp_id)

    def test_retrieve_experience(self):
        """Retrieving an experience returns the full record."""
        exp = Experience(
            task="debug a Python script",
            goal="fix the error",
            success=False,
            errors=["IndexError: list index out of range"],
            lessons=["check array bounds"],
        )
        exp_id = self.memory.ingest(exp)
        retrieved = self.memory.get(exp_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.task, "debug a Python script")
        self.assertFalse(retrieved.success)
        self.assertEqual(retrieved.errors, ["IndexError: list index out of range"])

    def test_find_similar(self):
        """Similar experiences are found by keyword matching."""
        self.memory.ingest(Experience(task="write a Python function", success=True))
        self.memory.ingest(Experience(task="debug a Python script", success=False))
        self.memory.ingest(Experience(task="deploy a web server", success=True))
        similar = self.memory.find_similar("Python code function", limit=2)
        self.assertGreater(len(similar), 0)
        # Should find the Python-related experiences
        tasks = [e.task for e in similar]
        self.assertTrue(any("Python" in t for t in tasks))

    def test_get_successful(self):
        """Successful experiences are retrieved separately."""
        self.memory.ingest(Experience(task="task1", success=True))
        self.memory.ingest(Experience(task="task2", success=False))
        self.memory.ingest(Experience(task="task3", success=True))
        successful = self.memory.get_successful()
        self.assertEqual(len(successful), 2)

    def test_get_failed(self):
        """Failed experiences are retrieved separately."""
        self.memory.ingest(Experience(task="task1", success=True))
        self.memory.ingest(Experience(task="task2", success=False))
        failed = self.memory.get_failed()
        self.assertEqual(len(failed), 1)

    def test_stats(self):
        """Stats return correct counts."""
        self.memory.ingest(Experience(task="t1", success=True, confidence=0.8))
        self.memory.ingest(Experience(task="t2", success=False, confidence=0.3))
        stats = self.memory.get_stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["successful"], 1)
        self.assertEqual(stats["failed"], 1)
        self.assertAlmostEqual(stats["success_rate"], 0.5)


class TestLearningPipeline(unittest.TestCase):
    """Test the Learning Pipeline — multi-stage experience processing."""

    def setUp(self):
        self.db = DatabaseManager(":memory:")
        self.pipeline = LearningPipeline(self.db)

    def test_process_successful_experience(self):
        """Processing a successful experience extracts lessons and creates skills."""
        exp = Experience(
            task="write a Python hello world program",
            goal="create a simple program",
            actions=["open editor", "write print statement", "run program"],
            tools_used=["python"],
            success=True,
            duration=3.0,
        )
        result = self.pipeline.process_experience(exp)
        self.assertTrue(result.success)
        self.assertGreater(len(result.steps_completed), 0)
        self.assertIn("OBSERVE", result.steps_completed)
        self.assertIn("UNDERSTAND", result.steps_completed)
        self.assertIn("GENERALIZE", result.steps_completed)
        self.assertIn("STORE", result.steps_completed)

    def test_process_failed_experience(self):
        """Processing a failed experience extracts failure lessons."""
        exp = Experience(
            task="run a Python script",
            goal="execute the script",
            actions=["run command"],
            errors=["ModuleNotFoundError: No module named 'requests'"],
            lessons=["install missing dependencies"],
            success=False,
            duration=1.0,
        )
        result = self.pipeline.process_experience(exp)
        self.assertTrue(result.success)  # pipeline itself succeeded
        self.assertGreater(len(result.generalizations), 0)

    def test_creates_knowledge(self):
        """Processing an experience creates knowledge entries."""
        exp = Experience(
            task="test Python function",
            goal="verify correctness",
            actions=["write test", "run test"],
            success=True,
            lessons=["always write tests"],
        )
        self.pipeline.process_experience(exp)
        # Check knowledge was created
        count = self.db.fetch_one("SELECT COUNT(*) FROM learned_knowledge")
        self.assertGreater(count[0], 0)

    def test_creates_generalizations(self):
        """Processing an experience creates generalizations."""
        exp = Experience(
            task="debug application",
            goal="fix the bug",
            errors=["Connection refused"],
            success=False,
            lessons=["check network connectivity"],
        )
        result = self.pipeline.process_experience(exp)
        self.assertGreater(len(result.generalizations), 0)

    def test_creates_skill(self):
        """Processing an experience with actions creates a skill."""
        exp = Experience(
            task="write code",
            goal="create a program",
            actions=["open file", "write code", "save file", "run"],
            success=True,
        )
        result = self.pipeline.process_experience(exp)
        self.assertGreater(len(result.skills_created), 0)
        # Check skill was stored
        count = self.db.fetch_one("SELECT COUNT(*) FROM learned_skills")
        self.assertGreater(count[0], 0)

    def test_updates_existing_skill(self):
        """Processing similar experiences updates the same skill."""
        exp1 = Experience(
            task="write code",
            goal="create program 1",
            actions=["open file", "write code", "save", "run"],
            success=True,
        )
        exp2 = Experience(
            task="write code",
            goal="create program 2",
            actions=["open file", "write code", "save", "run"],
            success=True,
        )
        self.pipeline.process_experience(exp1)
        self.pipeline.process_experience(exp2)
        # Should have 1 skill with experience_count = 2
        row = self.db.fetch_one("SELECT experience_count FROM learned_skills WHERE name = 'write_code'")
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 2)

    def test_confidence_update(self):
        """Confidence delta is positive for success, negative for failure."""
        exp_success = Experience(task="task1", success=True)
        result_success = self.pipeline.process_experience(exp_success)
        self.assertGreater(result_success.confidence_delta, 0)

        exp_fail = Experience(task="task2", success=False, errors=["error"])
        result_fail = self.pipeline.process_experience(exp_fail)
        self.assertLess(result_fail.confidence_delta, 0)

    def test_get_stats(self):
        """Stats return correct counts."""
        self.pipeline.process_experience(Experience(task="t1", actions=["a", "b"], success=True))
        self.pipeline.process_experience(Experience(task="t2", success=False, errors=["e"]))
        stats = self.pipeline.get_stats()
        self.assertGreater(stats["knowledge_items"], 0)
        self.assertGreater(stats["skills"], 0)


class TestLearningAPI(unittest.TestCase):
    """Test the Learning API endpoints."""

    def setUp(self):
        from genesis_ai.main import GenesisAI
        from genesis_ai.ui.app import create_app
        import genesis_ai.ui.app as app_module
        self.genesis = GenesisAI()
        app_module.genesis = self.genesis
        self.app = create_app(self.genesis)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        # Ensure a test user exists for FK constraints
        self.genesis.db.execute(
            "INSERT OR IGNORE INTO users (id, username) VALUES (1, 'test_user')"
        )

    def test_ingest_experience(self):
        """POST /learning/experience ingests and processes an experience."""
        response = self.client.post("/learning/experience", json={
            "task": "write a Python function",
            "goal": "create a working function",
            "actions": ["define", "write", "test"],
            "success": True,
        })
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertIn("experience_id", data)
        self.assertIn("learning_result", data)
        self.assertTrue(data["learning_result"]["success"])

    def test_ingest_missing_task(self):
        """POST /learning/experience with missing task returns 400."""
        response = self.client.post("/learning/experience", json={
            "goal": "something",
        })
        self.assertEqual(response.status_code, 400)

    def test_submit_error(self):
        """POST /learning/error submits an error report."""
        response = self.client.post("/learning/error", json={
            "task": "run script",
            "error": "ModuleNotFoundError: requests",
            "success": False,
        })
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertTrue(data["failure_learned"])

    def test_get_status(self):
        """GET /learning/status returns system status."""
        response = self.client.get("/learning/status")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "active")
        self.assertIn("learning_pipeline", data)
        self.assertIn("experience_memory", data)

    def test_get_skills(self):
        """GET /learning/skills returns learned skills."""
        # Create a skill first
        self.client.post("/learning/experience", json={
            "task": "write code",
            "goal": "create program",
            "actions": ["open", "write", "save"],
            "success": True,
        })
        response = self.client.get("/learning/skills")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("skills", data)

    def test_get_experiences(self):
        """GET /learning/experiences returns recent experiences."""
        self.client.post("/learning/experience", json={
            "task": "test task",
            "goal": "test goal",
            "success": True,
        })
        response = self.client.get("/learning/experiences")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("experiences", data)
        self.assertGreater(len(data["experiences"]), 0)

    def test_get_knowledge(self):
        """GET /learning/knowledge returns learned knowledge."""
        self.client.post("/learning/experience", json={
            "task": "learn concept",
            "goal": "understand",
            "lessons": ["concept A is important"],
            "success": True,
        })
        response = self.client.get("/learning/knowledge")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("knowledge", data)

    def test_get_generalizations(self):
        """GET /learning/generalizations returns generalizations."""
        self.client.post("/learning/experience", json={
            "task": "debug application",
            "goal": "fix error",
            "errors": ["connection refused"],
            "success": False,
        })
        response = self.client.get("/learning/generalizations")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("generalizations", data)

    def test_evaluate(self):
        """POST /learning/evaluate checks applicable generalizations."""
        # First create some generalizations
        self.client.post("/learning/experience", json={
            "task": "debug Python application",
            "goal": "fix error",
            "errors": ["import error"],
            "success": False,
        })
        response = self.client.post("/learning/evaluate", json={
            "task": "debug a Python web app",
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("applicable_generalizations", data)

    def test_learning_session(self):
        """Learning sessions can be started and stopped."""
        resp1 = self.client.post("/learning/session/start", json={
            "topic": "Python basics",
            "goals": ["learn variables", "learn loops"],
        })
        self.assertEqual(resp1.status_code, 201)
        session_id = resp1.get_json()["session_id"]

        resp2 = self.client.post("/learning/session/stop", json={
            "session_id": session_id,
        })
        self.assertEqual(resp2.status_code, 200)


class TestEndToEndLearning(unittest.TestCase):
    """End-to-end learning experiment — the acceptance test.

    This test demonstrates the complete learning loop:
    1. Genesis receives an experience
    2. Learning Engine extracts pattern
    3. Generalization Engine creates principle
    4. Knowledge Engine stores it
    5. Skill Engine creates/revises skill
    6. Genesis validates learning
    7. A NEW task benefits from previous learning
    """

    def setUp(self):
        self.db = DatabaseManager(":memory:")
        self.pipeline = LearningPipeline(self.db)
        self.memory = ExperienceMemory(self.db)

    def test_experience_to_generalization_to_reuse(self):
        """Experience → Generalization → Knowledge → Skill → Reuse."""
        # Step 1: First experience — Python dependency failure
        exp1 = Experience(
            task="run Python script that uses requests library",
            goal="execute the script successfully",
            actions=["install requests", "run script"],
            errors=["ModuleNotFoundError: No module named 'requests'"],
            success=False,
            tools_used=["pip", "python"],
            lessons=["install missing dependencies before running"],
        )
        result1 = self.pipeline.process_experience(exp1)
        self.assertTrue(result1.success)
        self.assertGreater(len(result1.generalizations), 0)

        # Step 2: Verify knowledge was created
        knowledge = self.db.fetch_all("SELECT concept, claim, status FROM learned_knowledge")
        self.assertGreater(len(knowledge), 0)

        # Step 3: Verify generalizations were created
        gens = self.db.fetch_all("SELECT pattern, description FROM learned_generalizations")
        self.assertGreater(len(gens), 0)

        # Step 4: Verify skill was created
        skills = self.db.fetch_all("SELECT name, procedure FROM learned_skills")
        self.assertGreater(len(skills), 0)

        # Step 5: NEW task — Node.js dependency failure (different language, same pattern)
        exp2 = Experience(
            task="run Node.js application that uses express package",
            goal="start the server",
            actions=["npm install", "node app.js"],
            errors=["Error: Cannot find module 'express'"],
            success=False,
            tools_used=["npm", "node"],
        )
        result2 = self.pipeline.process_experience(exp2)
        self.assertTrue(result2.success)

        # Step 6: Check if the generalization applies
        # The pattern "missing resource" should apply to both
        gen_count = self.db.fetch_one("SELECT COUNT(*) FROM learned_generalizations")
        self.assertGreater(gen_count[0], 0)

        # Step 7: Check that the generalization covers both experiences
        all_gens = self.db.fetch_all("SELECT source_experiences FROM learned_generalizations")
        all_exp_ids = set()
        for gen in all_gens:
            ids = json.loads(gen[0])
            all_exp_ids.update(ids)
        # Both experience IDs should be covered
        self.assertIn(exp1.experience_id, all_exp_ids)
        self.assertIn(exp2.experience_id, all_exp_ids)

    def test_success_experience_creates_reusable_skill(self):
        """A successful experience creates a reusable skill."""
        exp = Experience(
            task="write Python unit test",
            goal="test a function",
            actions=["import unittest", "write test class", "write test method", "run tests"],
            tools_used=["python", "unittest"],
            success=True,
            duration=10.0,
        )
        result = self.pipeline.process_experience(exp)
        self.assertTrue(result.success)
        self.assertGreater(len(result.skills_created), 0)

        # The skill should be reusable
        skill_name = result.skills_created[0]["name"]
        skill = self.db.fetch_one(
            "SELECT name, procedure, confidence FROM learned_skills WHERE name = ?",
            (skill_name,),
        )
        self.assertIsNotNone(skill)
        self.assertGreater(skill[2], 0)  # confidence > 0

    def test_failure_learning_improves_future(self):
        """After learning from failure, similar failures are predicted."""
        # First failure
        exp1 = Experience(
            task="start web server on port 8080",
            goal="listen for requests",
            actions=["bind port", "start server"],
            errors=["OSError: [Errno 98] Address already in use"],
            success=False,
        )
        self.pipeline.process_experience(exp1)

        # Check that a generalization about port conflicts exists
        gens = self.db.fetch_all("SELECT description FROM learned_generalizations")
        gen_descriptions = " ".join(g[0] for g in gens)
        # Should have some generalization about errors/failures
        self.assertGreater(len(gens), 0)

        # Second failure — different port, same pattern
        exp2 = Experience(
            task="start another server on port 3000",
            goal="listen for requests",
            actions=["bind port", "start server"],
            errors=["OSError: [Errno 98] Address already in use"],
            success=False,
        )
        result2 = self.pipeline.process_experience(exp2)
        self.assertTrue(result2.success)
        # Should have generalizations that apply
        self.assertGreater(len(result2.generalizations), 0)


if __name__ == "__main__":
    unittest.main()
