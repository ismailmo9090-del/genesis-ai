"""LanguageEngine — lightweight local LLM for natural response rephrasing.

This module provides a small, local language model as the FINAL composition
step — rephrasing Genesis's own verified facts into natural prose. This does
NOT replace Genesis's knowledge/retrieval/verification pipeline; it only
handles the "how do I phrase this naturally" step.

Model: Qwen2.5-0.5B-Instruct (loaded via transformers, CPU-only)
"""

from __future__ import annotations

import logging
import time
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level singleton to load model only once
_model_lock = threading.Lock()
_model = None
_tokenizer = None
_model_loaded = False
_model_load_error = None


def _load_model():
    """Load the language model once at startup."""
    global _model, _tokenizer, _model_loaded, _model_load_error

    if _model_loaded:
        return

    with _model_lock:
        if _model_loaded:
            return

        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM

            model_name = "Qwen/Qwen2.5-0.5B-Instruct"
            logger.info("Loading language model: %s", model_name)
            start = time.time()

            _tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
            _model = AutoModelForCausalLM.from_pretrained(
                model_name,
                dtype=torch.float32,
                trust_remote_code=True,
            )
            _model.eval()

            elapsed = time.time() - start
            logger.info("Language model loaded in %.1fs", elapsed)
            _model_loaded = True

        except Exception as e:
            logger.error("Failed to load language model: %s", e)
            _model_load_error = str(e)
            _model_loaded = False


def _ensure_model_loaded():
    """Ensure the model is loaded. Thread-safe, loads only once."""
    if not _model_loaded:
        _load_model()


class LanguageEngine:
    """Lightweight local LLM for natural response rephrasing.

    Usage:
        engine = LanguageEngine()
        natural = engine.compose_natural_response(
            query="what is photosynthesis?",
            verified_claims=["Photosynthesis is the process by which plants convert sunlight to energy"],
            language="english",
            tone_hint="normal",
        )
    """

    def __init__(self):
        _ensure_model_loaded()
        self.is_available = _model_loaded
        self._load_error = _model_load_error

    def compose_natural_response(
        self,
        query: str,
        verified_claims: list[str],
        language: str = "english",
        tone_hint: str = "normal",
    ) -> Optional[str]:
        """Rephrase verified claims into a natural, conversational response.

        Args:
            query: The original user question
            verified_claims: List of verified factual claims to incorporate
            language: Target language ('english', 'hindi', 'hinglish')
            tone_hint: Tone hint ('casual', 'formal', 'normal')

        Returns:
            Natural prose response, or None if model unavailable/error
        """
        if not self.is_available:
            return None

        if not verified_claims:
            return None

        try:
            import torch

            # Build the prompt
            claims_text = " ".join(verified_claims[:5])
            language_instruction = {
                "english": "English",
                "hindi": "Hindi",
                "hinglish": "Hinglish (mix of Hindi and English)",
            }.get(language, "English")

            tone_instruction = {
                "casual": "casual and friendly",
                "formal": "formal and professional",
                "normal": "clear and conversational",
            }.get(tone_hint, "clear and conversational")

            prompt = (
                f"You are rewriting factual information into a natural, conversational answer. "
                f"Use ONLY the facts provided below — do not add facts not listed here. "
                f"Write in flowing natural prose in {language_instruction}. "
                f"Keep the tone {tone_instruction}. "
                f"Avoid bullet points unless the facts are inherently list-like. "
                f"Do not say 'according to sources' — answer directly and naturally.\n\n"
                f"Question: {query}\n"
                f"Verified facts: {claims_text}\n"
                f"Natural answer:"
            )

            # Tokenize and generate
            start = time.time()
            messages = [{"role": "user", "content": prompt}]
            text = _tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = _tokenizer([text], return_tensors="pt")

            with torch.no_grad():
                outputs = _model.generate(
                    **inputs,
                    max_new_tokens=200,
                    temperature=0.7,
                    do_sample=True,
                    top_p=0.9,
                    repetition_penalty=1.1,
                )

            response = _tokenizer.decode(
                outputs[0][inputs.input_ids.shape[1]:],
                skip_special_tokens=True,
            )

            elapsed = time.time() - start
            logger.debug("Language model generation took %.2fs", elapsed)

            # Clean up the response
            response = response.strip()
            if not response:
                return None

            # Remove any trailing incomplete sentences
            if response and response[-1] not in ".!?।":
                last_period = max(
                    response.rfind("."),
                    response.rfind("!"),
                    response.rfind("?"),
                    response.rfind("।"),
                )
                if last_period > 0:
                    response = response[:last_period + 1]

            return response if response else None

        except Exception as e:
            logger.error("Language model generation failed: %s", e)
            return None

    def is_model_loaded(self) -> bool:
        """Check if the model is loaded."""
        return _model_loaded

    def get_model_info(self) -> dict:
        """Get information about the loaded model."""
        return {
            "loaded": _model_loaded,
            "error": _model_load_error,
            "model_name": "Qwen/Qwen2.5-0.5B-Instruct" if _model_loaded else None,
        }
