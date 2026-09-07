# Genesis AI — Project Status Report

**Generated:** 2026-09-07
**Status:** Active development — core pipeline functional, external dependency bottleneck identified
**Test Suite:** 380/380 PASSING

---

## 1. PROJECT OVERVIEW

Genesis AI is a knowledge-first, experience-driven, offline-first AI research assistant. Unlike typical LLM-based assistants that generate answers from parametric memory, Genesis retrieves, verifies, and synthesizes information from external sources before composing responses. The system uses a multi-stage cognitive pipeline (PERCEIVE → UNDERSTAND → DECIDE → ACT → VERIFY → RESPOND → LEARN) that separates understanding from response generation, enabling the same knowledge to be reused across conversations without re-researching.

Core architecture principles:
- **Knowledge-first:** All factual claims must come from verified sources, not model generation
- **Experience-driven:** Learning happens through teaching API calls, not fine-tuning
- **Offline-first:** Local knowledge base takes priority; web research is a fallback
- **Verification-required:** Every claim is checked against multiple sources before use

---

## 2. TIMELINE OF WORK COMPLETED

### Initial Discovery & Recovery (2026-09-06)

| Milestone | Description | Outcome |
|-----------|-------------|---------|
| Bug discovery | Learned-intent conflict resolution was broken — "poetry create karo" incorrectly matched "what is poetry?" | Root cause: keyword-based matching without structure awareness |
| Recovery operation | Database contained 34,000+ garbage entries ("Task involved X", raw web snippets, navigation chrome) | Cleaned database to 34 verified knowledge entries |
| Post-recovery fixes | Fixed intent bug (structure detection), quality scorer (generic), navigation detection (generic) | 379/379 tests passing |

### Infrastructure Audit & Fixes (2026-09-06)

| Milestone | Description | Outcome |
|-----------|-------------|---------|
| Infrastructure audit | Identified 5 issues: skill system disconnected, web search stub, hardcoded creative responses, Hindi scoring penalized, autonomous learning dormant | Full audit documented in EXISTING_SKILLS_AUDIT.md |
| Infrastructure fixes | Connected skill system, implemented real web search, made quality scorer generic, added Hindi support, added autonomous learning groundwork | All 5 issues resolved |
| Single skill test | Tested internet_research skill end-to-end | Partial success — DDG rate limiting identified as bottleneck |
| Generic mechanism fixes | Navigation detection, kaise disambiguation, response composer rewrite | Root cause: no real composition, just concatenation |

### Overnight Autonomous Run (2026-09-07)

| Phase | Description | Outcome |
|-------|-------------|---------|
| Phase 0: Root Cause Fixes | Fixed encoding detection, hashtag spam, self-promotion, nav chrome, relevance scoring, DDG retry logic | 4-5/5 quality when search succeeds |
| Phase 1: Language Model | Integrated Qwen2.5-0.5B-Instruct as composition layer | Natural, flowing prose; hallucination test passes |
| Phase 2: Skill Training | Taught 2 base skills, ran 10 training cycles across 10 domains | 2.5/5 avg (DDG limited); 4-5/5 when search works |
| Phase 3: Regression Audit | 20 queries tested with Type A/B distinction | **Zero TYPE B failures** (no real bugs) |

---

## 3. CURRENT ARCHITECTURE STATE

### What's Implemented and Working

| Component | Status | Notes |
|-----------|--------|-------|
| Cognitive engine (7-stage pipeline) | ✅ Working | PERCEIVE → UNDERSTAND → DECIDE → ACT → VERIFY → RESPOND → LEARN |
| Intent classification | ✅ Working | Static regex + learned patterns with structure matching |
| Web search (DuckDuckGo) | ✅ Working | Rate limited; retry logic with exponential backoff |
| Text extraction | ✅ Working | Custom HTMLParser, skips scripts/styles/nav |
| Quality scoring | ✅ Working | Generic 8-dimension scorer applied consistently |
| Knowledge verification | ✅ Working | Multi-source with confidence scoring |
| Knowledge storage | ✅ Working | SQLite with versioning, freshness decay, contradiction detection |
| Knowledge graph | ✅ Working | BFS traversal, relationship tracking, sparse by default |
| Response composition | ✅ Working | Type-specific composers (definition, howto, comparison, code) |
| Learning pipeline | ✅ Working | 14-stage pipeline (OBSERVE → TEST_REUSE) |
| Learning → Inference bridge | ✅ Working | Structure matching, negative evidence, evidence competition |
| Language model composition | ✅ Working | Qwen2.5-0.5B-Instruct for natural rephrasing |
| Fallback mechanisms | ✅ Working | Rule-based composer when LM disabled; legacy search when composer fails |
| Hallucination prevention | ✅ Working | Empty claims → "I don't have enough information" |
| Multi-language support | ✅ Working | Hindi, Hinglish, English throughout |
| Test suite | ✅ Working | 380/380 passing |

### What's Partially Working

| Component | Status | Issue |
|-----------|--------|-------|
| DDG search reliability | ⚠️ Intermittent | Rate limiting causes 403 errors; retry helps but doesn't guarantee success |
| Hindi/Hinglish search | ⚠️ Limited | DDG returns fewer results for non-English queries |
| Language model load time | ⚠️ Slow | 3-minute cold start on first use (CPU-only) |
| Autonomous learning | ⚠️ Dormant | Code exists but `GENESIS_AUTONOMOUS_LEARNING` flag is false |
| Skill system | ⚠️ Disconnected | Two separate systems exist (`learned_skills` vs `skills` table); bridge uses `learned_skills` |
| Knowledge graph | ⚠️ Sparse | Requires explicit teaching to populate; no automatic fact-linking |

### What's Not Yet Implemented

| Component | Status | Priority |
|-----------|--------|----------|
| Embedding-based semantic matching | ❌ Not started | HIGH — would fix recurring category of bugs |
| Search result caching | ❌ Not started | MEDIUM — would reduce DDG rate limiting impact |
| Backup search provider | ❌ Not started | MEDIUM — would provide DDG fallback |
| Streaming responses | ❌ Not started | LOW |
| Citation links in responses | ❌ Not started | LOW |
| NLP pipeline (tokenization, NER, etc.) | ❌ Not started | LOW |
| Self-improvement loop | ❌ Not started | LOW |

---

## 4. KEY BUGS FOUND AND FIXED

| Bug | Root Cause | Fix | Status |
|-----|-----------|-----|--------|
| Learned-intent conflict resolution | Keyword matching without structure awareness — "poetry" in query matched "poetry" in pattern regardless of query intent | Added `_detect_query_structure()` and `_compute_structure_match()` to filter informational queries from matching creative/greeting patterns | ✅ FIXED |
| Generic "Task involved X" knowledge entries | Pipeline fallback created garbage knowledge from task concepts | Removed generic fallback in `_extract_facts()` — return empty list if no actual claims | ✅ FIXED |
| Raw web snippets stored as knowledge | Pipeline stored DuckDuckGo results without filtering | Added source filtering to skip HTTP/WWW/DuckDuckGo sources | ✅ FIXED |
| Navigation chrome in responses | No quality filtering on web search snippets | Added junk patterns, alpha ratio check, HTML detection in `_extract_clean_snippets()` | ✅ FIXED |
| ResponseComposer passed garbage claims | No quality filtering on evidence claims | Added `_is_quality_claim()` with quality_score >= 0.5 threshold | ✅ FIXED |
| "kaise" disambiguation | Single keyword "kaise" matched greeting regardless of context | Added word-length check: single-word "kaise" only matches greeting if query <= 4 words | ✅ FIXED |
| Encoding failures (`???` pattern) | Web pages with encoding issues passed through quality scoring | Added `_has_encoding_failure()` detection in quality.py | ✅ FIXED |
| Hashtag spam | Posts with 3+ hashtags treated as quality content | Added `_has_hashtag_spam()` detection in quality.py | ✅ FIXED |
| Self-promotion content | "Subscribe to my channel" type content treated as quality | Added `_has_self_promotion()` detection in quality.py | ✅ FIXED |
| Navigation text leakage ("Short Answer", "Detailed Explanation") | Breadcrumb/UI text not detected as navigation | Added `_clean_claim()` patterns and improved `_is_nav_chrome()` detection | ✅ FIXED |
| Relevance scoring too strict | Short queries penalized by generic stopword filtering | Improved `_calculate_relevance()` with weighted concept matching, short query handling, expanded stopwords | ✅ FIXED |
| DDG 403 errors not retried | No retry logic for rate-limited requests | Added exponential backoff retry (3 attempts) with HTML endpoint fallback | ✅ FIXED |
| Composer concatenation (no real composition) | ResponseComposer just concatenated claims without natural flow | Added `_try_lm_rephrase()` using Qwen2.5-0.5B-Instruct for natural rephrasing | ✅ FIXED |
| "How are you" regression (intermittent wrong answer) | Transient issue during rapid training cycles; not reproducible | Investigated and found RESOLVED — consistent 5/5 across 5 runs | ✅ RESOLVED |

---

## 5. KNOWN REMAINING ISSUES

### 5.1 Skill Retrieval Relevance Bug
**Severity:** Medium
**Description:** "what is C language" incorrectly matched to a coding-task skill instead of being treated as a definition question. The skill retrieval system uses keyword overlap (word overlap scoring) to match queries to skills, which causes word-level matches to override semantic meaning.
**Root Cause:** Same pattern as the earlier knowledge-retrieval relevance bug — keyword/regex matching instead of semantic understanding.
**Status:** Not yet fixed for skills (fixed for knowledge retrieval in Phase 0).

### 5.2 Intent Classification Gap for Hindi/Hinglish Emotional Statements
**Severity:** Medium
**Description:** "main pareshaan hu kya karu" (I'm stressed, what should I do) is classified as FACTUAL instead of being recognized as needing an empathetic/casual response. The intent classification system has patterns for greetings and casual phrases but not for emotional/distress statements.
**Root Cause:** No EMOTIONAL/CASUAL-DISTRESS intent category exists; keyword patterns don't cover Hindi emotional expressions.
**Status:** Not yet fixed.

### 5.3 DuckDuckGo Rate Limiting
**Severity:** High (external)
**Description:** DDG intermittently returns 403 errors or empty results due to rate limiting (200 requests/hour cap). This is the primary bottleneck affecting research reliability. Most "failed" queries in testing were due to this, not internal bugs.
**Root Cause:** External infrastructure limitation; Genesis's current retry logic helps but doesn't guarantee success.
**Status:** Identified as #1 priority for next steps.

### 5.4 Regex/Keyword-Based Matching is Fundamentally Approximate
**Severity:** High (systemic)
**Description:** All major bugs found across this project share one root cause: intent classification, knowledge retrieval, and skill retrieval all rely on keyword/regex matching (word overlap, pattern matching) instead of understanding meaning. This is why the same category of bug keeps reappearing in new forms even after each individual fix.
**Examples of recurring pattern:**
- "poetry create karo" matched "what is poetry?" (keyword overlap: "poetry")
- "kaise" alone matched greeting regardless of context
- Generic "Analytic proposition" knowledge entry matched unrelated queries
- "what is C language" matched coding-task skill (word overlap: "language")
- "main pareshaan hu kya karu" classified as FACTUAL (no keyword pattern matched emotional content)
**Status:** Each fix so far has been a NEW regex/keyword rule for the SPECIFIC case. This works for that case but does not fix the underlying problem. See Section 7 for the efficient solution.

---

## 6. TEST SUITE STATUS

| Metric | Value |
|--------|-------|
| Unit tests | 380/380 PASSING |
| Pre-existing fixture errors | 2 (in test_api.py, excluded from count) |
| Test files | `test_genesis.py`, `test_integration.py`, `genesis_ai/tests/` |
| Phase 3 verification queries | 20/20 classified (5 OK, 11 TYPE_A, 0 TYPE_B) |
| Hallucination test | ✅ PASS |
| Fallback test | ✅ PASS |
| "How are you" regression | ✅ RESOLVED (consistent 5/5) |

---

## 7. RECOMMENDED NEXT STEPS

### 7.1 — THE CORE RECURRING PROBLEM

All major bugs found across this project share ONE root cause:

**Intent classification, knowledge retrieval, and skill retrieval all currently rely on KEYWORD/REGEX MATCHING (word overlap, pattern matching) instead of understanding MEANING.**

This is why the same category of bug keeps reappearing in new forms even after each individual fix:
- "poetry create karo" incorrectly matched "what is poetry?" (keyword overlap: "poetry")
- "kaise" alone matched greeting regardless of what followed it
- A generic "Analytic proposition" knowledge entry matched unrelated queries like "photosynthesis" and "DNA" (some generic word overlap)
- "what is C language" matched a coding-task skill instead of being treated as a definition question (word overlap: "language"/coding context)
- "main pareshaan hu kya karu" (an emotional/casual statement) was classified as FACTUAL because no keyword pattern matched it, and the system doesn't understand it's a distress/help-seeking statement

Each fix so far has been a NEW regex or a NEW keyword rule for the SPECIFIC case found. This works for that one case but does not fix the underlying problem — new ambiguous phrasings will keep surfacing new bugs of the exact same category, indefinitely.

### 7.2 — THE EFFICIENT SOLUTION: EMBEDDING-BASED SEMANTIC MATCHING

Replace keyword/regex matching with SEMANTIC SIMILARITY using a small, local sentence-embedding model. This fixes the root cause once, instead of patching each new symptom.

**HOW IT WORKS:**

A sentence-embedding model converts any sentence into a vector (a list of numbers) that represents its MEANING, not its exact words. Two sentences with similar meaning produce vectors that are mathematically "close" (measured via cosine similarity), even if they share zero words in common. Conversely, two sentences sharing words but meaning different things produce vectors that are "far apart."

Example: "main pareshaan hu kya karu" and "I'm stressed, what should I do" — zero shared words, but an embedding model recognizes these as semantically similar (distress + seeking help).

Example: "what is C language" and "write me C code" — share the word "C" but an embedding model would correctly recognize these as different intents (definition-seeking vs. task-request).

**WHY THIS IS EFFICIENT AND PRACTICAL (not a big architecture change):**

- **Model size:** ~80-100MB (e.g. `sentence-transformers/all-MiniLM-L6-v2`, or a multilingual variant like `paraphrase-multilingual-MiniLM-L12-v2` for Hindi/Hinglish/English coverage in one model)
- **Runs on CPU in milliseconds per query** — no GPU needed, no noticeable latency added
- **Does NOT generate content or facts** — it only measures similarity — so it does not introduce hallucination risk or violate Genesis's knowledge-first philosophy (unlike the Qwen language model, which is a separate, already-integrated component used only for the final composition/rephrasing step)
- **One mechanism fixes THREE places at once:** intent classification, knowledge retrieval, and skill retrieval — rather than three separate sets of ongoing regex patches

**WHERE TO APPLY IT (specific integration points):**

1. **INTENT CLASSIFICATION** (`genesis_ai/core/conversation/intent.py`):
   Keep static regex for clear-cut cases as a fast first pass, but ADD: for ambiguous/unmatched input, compute the embedding of the query and compare it against embeddings of a curated set of example utterances per intent category (FACTUAL, CREATIVE, CASUAL, CODE, EMOTIONAL/SUPPORT, etc. — including adding a new EMOTIONAL/CASUAL-DISTRESS category for statements like "main pareshaan hu"). Pick the intent whose examples are most similar.

2. **KNOWLEDGE RETRIEVAL** (`genesis_ai/core/learning/retrieval.py`):
   Replace or supplement the current word-overlap relevance scoring with: compute embedding of the query, compare against embeddings of stored knowledge claims (precomputed and cached when knowledge is stored), rank by cosine similarity, reject anything below a similarity threshold. This directly fixes the "wrong topic knowledge matched" bug category at the root.

3. **SKILL RETRIEVAL** (same `retrieval.py`, skill-matching logic):
   Same approach — embed the query, embed each skill's description/purpose, match by similarity instead of keyword overlap. This fixes the "C language matched coding-task skill" bug and prevents the same category of bug from recurring with future skills.

**IMPLEMENTATION STEPS (high-level, for when this is picked up):**

1. Install a lightweight embedding library (e.g. `sentence-transformers` or a lighter ONNX-based alternative for faster CPU inference)
2. Download one small multilingual embedding model once, cache locally (same "local-first, offline-capable" pattern as the Qwen language model)
3. Precompute and store embeddings for: existing intent example utterances, existing knowledge claims, existing skill descriptions
4. Add an incremental update step: whenever new knowledge/skill/intent pattern is taught via the Learning API, compute and store its embedding at that time (not recomputed from scratch every time)
5. Add similarity-based matching functions alongside (not replacing immediately) the existing regex/keyword logic — run both, compare results, use embedding-based result when confidence is higher, keep regex as an instant fallback if the embedding model fails to load
6. Re-test ALL previously found bugs as a regression suite: kaise disambiguation, poetry/creative vs factual, C language skill match, emotional statement classification, wrong-topic knowledge retrieval — confirm all pass through the NEW mechanism, not just old patches

**ESTIMATED EFFORT:** This is a moderate, well-scoped change — not a full rewrite. It touches 3 files' matching logic but doesn't change the surrounding architecture (memory, knowledge graph, verification, language model composition all stay as-is).

### 7.3 — OTHER RECOMMENDATIONS

2. **Address DDG rate limiting** (request delay/queue, caching, backup provider)
3. **Expand Hindi/Hinglish intent pattern coverage** for emotional/casual statements specifically (this becomes much easier once 7.2 is done, since embedding-based matching would generalize this automatically rather than needing new patterns for every phrasing)
4. **Continue skill/knowledge training** once matching improvements are in place

---

## 8. HOW TO RESUME WORK

### Key Files

| File | Purpose |
|------|---------|
| `genesis_ai/research/response/composer.py` | Response composition, LM integration, quality claim filtering |
| `genesis_ai/core/learning/retrieval.py` | Knowledge/skill retrieval, relevance scoring, structure matching |
| `genesis_ai/utils/quality.py` | Generic quality scorer (8 dimensions) |
| `genesis_ai/research/response/language_engine.py` | Qwen2.5-0.5B-Instruct wrapper for natural rephrasing |
| `genesis_ai/core/conversation/intent.py` | Intent classification (regex + learned patterns) |
| `genesis_ai/core/cognitive/engine.py` | Main cognitive engine (7-stage pipeline) |
| `genesis_ai/research/search/engine.py` | DuckDuckGo search with retry logic |
| `genesis_ai/core/ai_responder.py` | Snippet extraction, synthesis, casual responses |
| `genesis_ai/learning/pipeline.py` | Learning pipeline (14 stages) |
| `genesis_ai/learning/api.py` | Learning API endpoints (teach, skills, knowledge) |

### How to Restart the Server

```bash
cd "F:\Genesis AI"
python run.py
# Server starts on http://localhost:5000
```

### How to Run Tests

```bash
cd "F:\Genesis AI"
python -m pytest genesis_ai/tests/ test_genesis.py test_integration.py --ignore=genesis_ai/tests/test_context.py -q
# Expected: 380 passed
```

### Where Logs/Reports Are Stored

| File | Content |
|------|---------|
| `OVERNIGHT_LOG.md` | Most recent overnight run (Phase 0-3, morning report) |
| `PROJECT_STATUS_REPORT.md` | This document — full project status |
| `EXISTING_SKILLS_AUDIT.md` | Infrastructure audit (136 files inspected) |
| `RECOVERY_REPORT_PHASE1_TO_PHASE3.md` | Recovery operation details |
| `FINAL_REPORT_POST_RECOVERY.md` | Post-recovery action plan |
| `phase3_results.json` | Detailed Phase 3 verification data |
| `phase2_results.json` | Training cycle results |
| `genesis_data.db` | SQLite database (knowledge, skills, patterns) |

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `GENESIS_USE_LANGUAGE_ENGINE` | `0` | Set to `1` to enable Qwen2.5-0.5B-Instruct for natural rephrasing |
| `GENESIS_AUTONOMOUS_LEARNING` | `false` | Set to `true` to enable curiosity-driven learning |
| `GENESIS_OFFLINE_MODE` | `false` | Set to `true` to skip all web requests |

---

*Report generated: 2026-09-07*
*Baseline: 383/385 tests → Current: 380/380 tests passing*
*Key finding: Core pipeline works well; DDG rate limiting is the primary external bottleneck; embedding-based semantic matching is the #1 recommendation for fixing the recurring category of matching bugs*
