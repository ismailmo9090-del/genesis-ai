"""Tests for Curriculum Engine and Learning Firewall."""

import time
import unittest

from genesis_ai.database.db import DatabaseManager
from genesis_ai.learning.curriculum import CurriculumEngine, Level, SkillProfile
from genesis_ai.learning.firewall import LearningFirewall, RiskLevel, FirewallRule, ActionCategory


class TestCurriculumEngine(unittest.TestCase):
    """Test the Curriculum Engine — adaptive difficulty and progression."""

    def setUp(self):
        self.db = DatabaseManager(":memory:")
        self.curriculum = CurriculumEngine(self.db)

    def test_new_domain_starts_beginner(self):
        """New domain starts at beginner level."""
        profile = self.curriculum.get_profile("python")
        self.assertEqual(profile.level, Level.BEGINNER)
        self.assertEqual(profile.total_tasks, 0)

    def test_success_increases_score(self):
        """Successful tasks increase the success score."""
        profile = self.curriculum.record_task("python", success=True)
        self.assertEqual(profile.total_tasks, 1)
        self.assertEqual(profile.successful_tasks, 1)
        self.assertGreater(profile.success_score, 0)

    def test_failure_decreases_score(self):
        """Failed tasks decrease the success score."""
        profile = self.curriculum.record_task("python", success=True)
        score_after_success = profile.success_score
        profile = self.curriculum.record_task("python", success=False)
        self.assertLess(profile.success_score, score_after_success)

    def test_streak_increases(self):
        """Streak increases on consecutive successes."""
        self.curriculum.record_task("python", success=True)
        self.curriculum.record_task("python", success=True)
        profile = self.curriculum.record_task("python", success=True)
        self.assertEqual(profile.streak, 3)
        self.assertEqual(profile.best_streak, 3)

    def test_failure_resets_streak(self):
        """Failure resets streak to 0."""
        self.curriculum.record_task("python", success=True)
        self.curriculum.record_task("python", success=True)
        self.curriculum.record_task("python", success=False)
        profile = self.curriculum.get_profile("python")
        self.assertEqual(profile.streak, 0)

    def test_level_advancement(self):
        """Score above threshold advances level."""
        # Record enough successes to reach intermediate
        for _ in range(12):
            self.curriculum.record_task("python", success=True)
        profile = self.curriculum.get_profile("python")
        self.assertEqual(profile.level, Level.INTERMEDIATE)

    def test_level_regression_on_failures(self):
        """Too many failures can regress level."""
        # Build up to intermediate
        for _ in range(12):
            self.curriculum.record_task("python", success=True)
        profile = self.curriculum.get_profile("python")
        self.assertEqual(profile.level, Level.INTERMEDIATE)

        # Now fail a lot to drop score
        for _ in range(10):
            self.curriculum.record_task("python", success=False)
        profile = self.curriculum.get_profile("python")
        # Should have regressed
        self.assertIn(profile.level, [Level.BEGINNER, Level.INTERMEDIATE])

    def test_recommendation_for_new_domain(self):
        """New domain gets introductory recommendation."""
        rec = self.curriculum.recommend("javascript")
        self.assertEqual(rec.current_level, Level.BEGINNER)
        self.assertGreater(len(rec.recommended_tasks), 0)
        self.assertEqual(rec.recommended_tasks[0]["type"], "introduction")

    def test_recommendation_for_streak(self):
        """On a streak, recommend challenges."""
        for _ in range(5):
            self.curriculum.record_task("python", success=True)
        rec = self.curriculum.recommend("python")
        task_types = [t["type"] for t in rec.recommended_tasks]
        self.assertIn("challenge", task_types)

    def test_recommendation_when_struggling(self):
        """When struggling, recommend easier practice."""
        for _ in range(5):
            self.curriculum.record_task("python", success=False)
        rec = self.curriculum.recommend("python")
        task_types = [t["type"] for t in rec.recommended_tasks]
        self.assertIn("practice", task_types)
        self.assertIn("review", task_types)

    def test_multiple_domains_independent(self):
        """Different domains have independent profiles."""
        self.curriculum.record_task("python", success=True)
        self.curriculum.record_task("python", success=True)
        self.curriculum.record_task("javascript", success=True)

        py_profile = self.curriculum.get_profile("python")
        js_profile = self.curriculum.get_profile("javascript")
        self.assertEqual(py_profile.total_tasks, 2)
        self.assertEqual(js_profile.total_tasks, 1)

    def test_get_all_profiles(self):
        """All profiles for a user are returned."""
        self.curriculum.record_task("python", success=True)
        self.curriculum.record_task("javascript", success=True)
        profiles = self.curriculum.get_all_profiles()
        self.assertEqual(len(profiles), 2)

    def test_domain_stats(self):
        """Domain stats include profile and recommendation."""
        self.curriculum.record_task("python", success=True)
        self.curriculum.record_task("python", success=False)
        stats = self.curriculum.get_domain_stats("python")
        self.assertIn("profile", stats)
        self.assertIn("outcomes", stats)
        self.assertIn("recommendation", stats)
        self.assertEqual(stats["outcomes"]["success"], 1)
        self.assertEqual(stats["outcomes"]["failure"], 1)

    def test_reset_domain(self):
        """Reset clears all progress for a domain."""
        self.curriculum.record_task("python", success=True)
        self.curriculum.record_task("python", success=True)
        self.curriculum.reset_domain("python")
        profile = self.curriculum.get_profile("python")
        self.assertEqual(profile.total_tasks, 0)
        self.assertEqual(profile.success_score, 0.0)

    def test_history_limited_to_20(self):
        """History keeps only last 20 entries."""
        for _ in range(25):
            self.curriculum.record_task("python", success=True)
        profile = self.curriculum.get_profile("python")
        self.assertEqual(len(profile.history), 20)


class TestLearningFirewall(unittest.TestCase):
    """Test the Learning Firewall — safety layer."""

    def setUp(self):
        self.db = DatabaseManager(":memory:")
        self.firewall = LearningFirewall(self.db)

    def test_read_actions_allowed(self):
        """Read actions are allowed by default."""
        verdict = self.firewall.check("get_knowledge")
        self.assertTrue(verdict.allowed)
        self.assertEqual(verdict.risk_level, RiskLevel.SAFE)

    def test_ingest_allowed(self):
        """Ingesting experiences is allowed."""
        verdict = self.firewall.check("ingest_experience")
        self.assertTrue(verdict.allowed)

    def test_learn_allowed(self):
        """Learning actions are allowed."""
        verdict = self.firewall.check("learn_from_interaction")
        self.assertTrue(verdict.allowed)

    def test_delete_requires_approval(self):
        """Delete actions require approval."""
        verdict = self.firewall.check("delete_knowledge")
        self.assertFalse(verdict.allowed)
        self.assertTrue(verdict.requires_approval)
        self.assertEqual(verdict.risk_level, RiskLevel.HIGH)

    def test_system_actions_blocked(self):
        """System actions are blocked."""
        verdict = self.firewall.check("execute_command")
        self.assertFalse(verdict.allowed)
        self.assertEqual(verdict.risk_level, RiskLevel.CRITICAL)

    def test_external_requires_approval(self):
        """External actions require approval."""
        verdict = self.firewall.check("send_data")
        self.assertFalse(verdict.allowed)
        self.assertTrue(verdict.requires_approval)

    def test_approval_flow(self):
        """Actions can be approved after request."""
        verdict = self.firewall.check("delete_knowledge")
        self.assertFalse(verdict.allowed)

        # Approve
        self.firewall.approve("delete_knowledge")
        verdict = self.firewall.check("delete_knowledge")
        self.assertTrue(verdict.allowed)

    def test_deny_flow(self):
        """Actions can be denied."""
        self.firewall.check("delete_knowledge")
        self.firewall.deny("delete_knowledge")
        # After denial, a new check should still require approval
        verdict = self.firewall.check("delete_knowledge")
        self.assertFalse(verdict.allowed)

    def test_pending_approvals(self):
        """Pending approvals are listed."""
        self.firewall.check("delete_knowledge")
        self.firewall.check("send_data")
        pending = self.firewall.get_pending_approvals()
        self.assertGreaterEqual(len(pending), 2)

    def test_firewall_log(self):
        """Firewall checks are logged."""
        self.firewall.check("get_knowledge")
        self.firewall.check("delete_knowledge")
        log = self.firewall.get_log()
        self.assertGreaterEqual(len(log), 2)

    def test_custom_rule(self):
        """Custom rules can be added."""
        self.firewall.add_rule(FirewallRule(
            name="custom_block",
            pattern=r"^custom_dangerous",
            category=ActionCategory.SYSTEM,
            risk_level=RiskLevel.CRITICAL,
            action="block",
        ))
        verdict = self.firewall.check("custom_dangerous_action")
        self.assertFalse(verdict.allowed)

    def test_stats(self):
        """Stats return correct counts."""
        self.firewall.check("get_knowledge")
        self.firewall.check("delete_knowledge")
        stats = self.firewall.get_stats()
        self.assertGreater(stats["total_checks"], 0)
        self.assertGreater(stats["blocked"], 0)

    def test_update_requires_approval(self):
        """Update actions require approval."""
        verdict = self.firewall.check("update_knowledge")
        self.assertFalse(verdict.allowed)
        self.assertTrue(verdict.requires_approval)

    def test_skill_create_allowed(self):
        """Creating skills is allowed."""
        verdict = self.firewall.check("skill_create")
        self.assertTrue(verdict.allowed)

    def test_search_allowed(self):
        """Search actions are allowed."""
        verdict = self.firewall.check("search_knowledge")
        self.assertTrue(verdict.allowed)


if __name__ == "__main__":
    unittest.main()
