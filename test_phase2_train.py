"""Phase 2 — Core Skill Training Script.

Teaches Genesis skills and knowledge across multiple domains,
tests queries, scores responses, and logs results.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import os
os.environ["GENESIS_USE_LANGUAGE_ENGINE"] = "0"  # Disable LM for faster training

import json
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.WARNING)

from genesis_ai.main import GenesisAI
from genesis_ai.learning.pipeline import LearningPipeline
from genesis_ai.learning.experience_memory import ExperienceMemory, Experience

# Initialize
genesis = GenesisAI()
genesis.db.init_db()
pipeline = LearningPipeline(genesis.db)
exp_memory = ExperienceMemory(genesis.db)

# Get baseline stats
status = genesis.get_status()
print(f"Baseline: knowledge={status['knowledge_count']}, concepts={status['concept_count']}, skills={status['skill_count']}")

# ── Step 2.1: Teach base skills ──
print("\n=== TEACHING BASE SKILLS ===")

# Skill 1: internet_research
try:
    genesis.db.execute(
        """INSERT INTO learned_skills
           (skill_id, name, description, purpose, procedure, confidence,
            experience_count, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)""",
        (
            "sk_research",
            "internet_research",
            "Search the internet, extract clean relevant content, and verify it before using",
            "Find accurate, high-quality information on any topic when local knowledge is insufficient",
            json.dumps([
                "Identify the core topic and strip filler words from the query",
                "Search using multiple phrasings if the first search doesn't return good results",
                "Prefer reliable sources over blogs/spam/social media content",
                "Extract only complete, coherent, relevant sentences",
                "Cross-check facts across multiple sources when possible",
                "Reject content with encoding errors, hashtags, or self-promotional language",
            ]),
            0.8,
            time.time(),
            time.time(),
        ),
    )
    print("✓ Taught skill: internet_research")
except Exception as e:
    print(f"✗ Failed to teach internet_research: {e}")

# Skill 2: conversational_response_composition
try:
    genesis.db.execute(
        """INSERT INTO learned_skills
           (skill_id, name, description, purpose, procedure, confidence,
            experience_count, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)""",
        (
            "sk_compose",
            "conversational_response_composition",
            "Transform researched facts into natural, human-like conversational responses",
            "Make responses feel like a knowledgeable person explaining something",
            json.dumps([
                "Never copy raw web text — always express in natural, flowing language",
                "Match the user's language and tone (Hindi/Hinglish/English, casual/formal)",
                "Keep length proportional to question complexity",
                "Never fabricate information beyond what was verified",
                "If information is unavailable, say so honestly and naturally",
            ]),
            0.8,
            time.time(),
            time.time(),
        ),
    )
    print("✓ Taught skill: conversational_response_composition")
except Exception as e:
    print(f"✗ Failed to teach conversational_response_composition: {e}")

# ── Training Domains ──
domains = [
    {
        "name": "science_basics",
        "experience": {
            "task": "Explain basic science concepts clearly",
            "goal": "factual",
            "context": {"domain": "science", "subtopic": "basic_concepts"},
            "observations": ["Users ask 'what is X' for fundamental concepts", "Need simple, accurate definitions"],
            "actions": ["search", "extract", "compose"],
            "result": {"outcome": "success", "quality": 4},
        },
        "queries": [
            ("what is gravity?", "english", "definition"),
            ("why is the sky blue?", "english", "cause"),
            ("how do plants grow?", "english", "mechanism"),
            ("prithvakarsh kya hai?", "hindi", "definition"),
        ],
    },
    {
        "name": "everyday_howto",
        "experience": {
            "task": "Provide how-to guidance for everyday tasks",
            "goal": "informational",
            "context": {"domain": "everyday_life", "subtopic": "how_to"},
            "observations": ["Users want step-by-step instructions", "Need practical, actionable advice"],
            "actions": ["search", "extract", "organize_steps"],
            "result": {"outcome": "success", "quality": 4},
        },
        "queries": [
            ("how to make tea?", "english", "howto"),
            ("how to study effectively?", "english", "howto"),
            ("kaise padhai karein?", "hinglish", "howto"),
            ("how to sleep better?", "english", "howto"),
        ],
    },
    {
        "name": "comparisons",
        "experience": {
            "task": "Compare two or more things clearly",
            "goal": "informational",
            "context": {"domain": "general_knowledge", "subtopic": "comparisons"},
            "observations": ["Users want to understand differences", "Need balanced comparison"],
            "actions": ["search", "compare", "contrast"],
            "result": {"outcome": "success", "quality": 4},
        },
        "queries": [
            ("what is the difference between LCD and LED?", "english", "comparison"),
            ("python vs java which is better?", "english", "comparison"),
            ("tea or coffee which is healthier?", "english", "comparison"),
            ("accha konsa hai?", "hinglish", "generic"),
        ],
    },
    {
        "name": "health_basics",
        "experience": {
            "task": "Explain basic health concepts",
            "goal": "factual",
            "context": {"domain": "health", "subtopic": "basic_concepts"},
            "observations": ["Users ask about common health topics", "Need accurate but accessible information"],
            "actions": ["search", "verify", "explain"],
            "result": {"outcome": "success", "quality": 4},
        },
        "queries": [
            ("what is diabetes?", "english", "definition"),
            ("why do we need sleep?", "english", "cause"),
            ("how does exercise help?", "english", "mechanism"),
            ("vitamin D kya hai?", "hinglish", "definition"),
        ],
    },
    {
        "name": "technology",
        "experience": {
            "task": "Explain technology concepts",
            "goal": "factual",
            "context": {"domain": "technology", "subtopic": "concepts"},
            "observations": ["Users ask about tech terms and concepts", "Need clear, jargon-free explanations"],
            "actions": ["search", "simplify", "explain"],
            "result": {"outcome": "success", "quality": 4},
        },
        "queries": [
            ("what is cloud computing?", "english", "definition"),
            ("how does WiFi work?", "english", "mechanism"),
            ("what is AI?", "english", "definition"),
            ("blockchain kya hai?", "hinglish", "definition"),
        ],
    },
    {
        "name": "cooking",
        "experience": {
            "task": "Explain cooking concepts and techniques",
            "goal": "informational",
            "context": {"domain": "cooking", "subtopic": "techniques"},
            "observations": ["Users ask about cooking methods", "Need practical cooking guidance"],
            "actions": ["search", "extract_steps", "guide"],
            "result": {"outcome": "success", "quality": 4},
        },
        "queries": [
            ("how to make pasta?", "english", "howto"),
            ("what is sautéing?", "english", "definition"),
            ("biryani kaise banate hain?", "hindi", "howto"),
            ("how to make rice?", "english", "howto"),
        ],
    },
    {
        "name": "nature_environment",
        "experience": {
            "task": "Explain natural phenomena and environmental topics",
            "goal": "factual",
            "context": {"domain": "nature", "subtopic": "phenomena"},
            "observations": ["Users ask about weather, nature, environment", "Need clear scientific explanations"],
            "actions": ["search", "explain_phenomenon"],
            "result": {"outcome": "success", "quality": 4},
        },
        "queries": [
            ("why do leaves change color?", "english", "cause"),
            ("how do rainbows form?", "english", "mechanism"),
            ("what causes earthquakes?", "english", "cause"),
            ("barish kaise hoti hai?", "hindi", "mechanism"),
        ],
    },
    {
        "name": "space_astronomy",
        "experience": {
            "task": "Explain space and astronomy concepts",
            "goal": "factual",
            "context": {"domain": "space", "subtopic": "astronomy"},
            "observations": ["Users ask about planets, stars, universe", "Need awe-inspiring but accurate explanations"],
            "actions": ["search", "verify", "explain"],
            "result": {"outcome": "success", "quality": 4},
        },
        "queries": [
            ("what is a black hole?", "english", "definition"),
            ("how far is the sun?", "english", "fact"),
            ("why do we have seasons?", "english", "cause"),
            ("mars kya hai?", "hinglish", "definition"),
        ],
    },
    {
        "name": "history_culture",
        "experience": {
            "task": "Explain historical events and cultural concepts",
            "goal": "factual",
            "context": {"domain": "history", "subtopic": "events"},
            "observations": ["Users ask about historical events", "Need accurate, contextual explanations"],
            "actions": ["search", "contextualize", "narrate"],
            "result": {"outcome": "success", "quality": 4},
        },
        "queries": [
            ("what was the industrial revolution?", "english", "definition"),
            ("who invented the telephone?", "english", "person"),
            ("Independence Day kab manaya jata hai?", "hinglish", "fact"),
            ("world war 2 kya tha?", "hinglish", "definition"),
        ],
    },
    {
        "name": "math_concepts",
        "experience": {
            "task": "Explain mathematical concepts",
            "goal": "factual",
            "context": {"domain": "mathematics", "subtopic": "concepts"},
            "observations": ["Users ask about math concepts", "Need clear, intuitive explanations"],
            "actions": ["search", "simplify", "give_examples"],
            "result": {"outcome": "success", "quality": 4},
        },
        "queries": [
            ("what is calculus?", "english", "definition"),
            ("how do you solve quadratic equations?", "english", "howto"),
            ("what is probability?", "english", "definition"),
            ("algebra kya hai?", "hinglish", "definition"),
        ],
    },
]

# ── Run Training Cycles ──
results_log = []
query_counter = 0

for cycle_idx, domain in enumerate(domains):
    print(f"\n=== CYCLE {cycle_idx + 1}: {domain['name']} ===")

    # Teach experience
    try:
        exp_data = domain["experience"]
        experience = Experience(
            task=exp_data["task"],
            goal=exp_data["goal"],
            context=exp_data["context"],
            observations=exp_data["observations"],
            actions=exp_data["actions"],
            tools_used=[],
            errors=[],
            attempts=[],
            result=exp_data["result"],
            success=True,
            evidence=[],
            reflection=exp_data["task"],
            metadata={"domain": domain["name"], "cycle": cycle_idx + 1},
        )
        pipeline.process_experience(experience)
        print(f"  ✓ Experience taught for {domain['name']}")
    except Exception as e:
        print(f"  ✗ Failed to teach experience: {e}")

    # Test queries
    cycle_scores = []
    for query_text, lang, q_type in domain["queries"]:
        query_counter += 1
        try:
            result = genesis.chat(f"trainer_{cycle_idx}", query_text)
            resp = result.get("response_text", "")
            intent = result.get("intent", "")
            confidence = result.get("confidence", 0)

            # Score response (1-5 rubric)
            score = 1
            if not resp or len(resp) < 20:
                score = 1
            elif "I don't have enough information" in resp:
                score = 2
            elif len(resp) < 50:
                score = 2
            elif any(garble in resp for garble in ["???", "###", "<<<"]):
                score = 1
            elif len(resp) > 100 and confidence > 0.3:
                score = 4
            elif len(resp) > 50:
                score = 3
            else:
                score = 3

            # Bonus for natural language
            if any(phrase in resp.lower() for phrase in ["the process", "this is because", "essentially", "in other words"]):
                score = min(5, score + 1)

            cycle_scores.append(score)
            print(f"  [{query_counter}] Q: {query_text[:40]}... | Score: {score}/5 | Intent: {intent} | Conf: {confidence:.2f}")
            print(f"      Response: {resp[:100]}...")

        except Exception as e:
            print(f"  [{query_counter}] Q: {query_text[:40]}... | ERROR: {e}")
            cycle_scores.append(1)

        time.sleep(0.5)

    avg_score = sum(cycle_scores) / len(cycle_scores) if cycle_scores else 0
    results_log.append({
        "cycle": cycle_idx + 1,
        "domain": domain["name"],
        "scores": cycle_scores,
        "avg_score": avg_score,
    })
    print(f"  Average score: {avg_score:.1f}/5")

    # Regression check every 3rd cycle
    if (cycle_idx + 1) % 3 == 0:
        print("\n  --- Regression Check ---")
        reg_queries = ["what is photosynthesis?", "kaise ho aap?", "how are you"]
        for rq in reg_queries:
            try:
                rr = genesis.chat("regression", rq)
                rresp = rr.get("response_text", "")
                print(f"    Regression: {rq[:30]}... → {rresp[:60]}...")
            except Exception as e:
                print(f"    Regression: {rq[:30]}... → ERROR: {e}")

# ── Final Stats ──
print("\n=== FINAL STATS ===")
final_status = genesis.get_status()
print(f"Knowledge: {status['knowledge_count']} → {final_status['knowledge_count']}")
print(f"Concepts: {status['concept_count']} → {final_status['concept_count']}")
print(f"Skills: {status['skill_count']} → {final_status['skill_count']}")

# ── Summary ──
print("\n=== TRAINING SUMMARY ===")
all_scores = []
for r in results_log:
    all_scores.extend(r["scores"])
    print(f"  Cycle {r['cycle']:2d} ({r['domain']:25s}): avg={r['avg_score']:.1f}/5, scores={r['scores']}")

overall_avg = sum(all_scores) / len(all_scores) if all_scores else 0
print(f"\nOverall average: {overall_avg:.1f}/5 across {len(all_scores)} queries")

# Save results
with open("phase2_results.json", "w") as f:
    json.dump({
        "baseline": status,
        "final": final_status,
        "results": results_log,
        "overall_avg": overall_avg,
        "total_queries": len(all_scores),
    }, f, indent=2)
print("\nResults saved to phase2_results.json")
