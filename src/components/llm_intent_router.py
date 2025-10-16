"""
LLM Intent Router - Hybrid component for RASA
Combines traditional NLU predictions with Ollama LLM
"""

import logging
from typing import Any, Dict, List, Optional, Text, Tuple

from rasa.engine.graph import ExecutionContext, GraphComponent
from rasa.engine.recipes.default_recipe import DefaultV1Recipe
from rasa.engine.storage.resource import Resource
from rasa.engine.storage.storage import ModelStorage
from rasa.shared.nlu.training_data.message import Message

# Import Ollama client
from .ollama_client import OllamaClient

logger = logging.getLogger(__name__)


@DefaultV1Recipe.register(
    DefaultV1Recipe.ComponentType.INTENT_CLASSIFIER, is_trainable=False
)
class LLMIntentRouter(GraphComponent):
    """
    Hybrid component that combines RASA NLU classifications with Ollama LLM
    to improve intent detection accuracy
    """

    def __init__(self, config: Dict[Text, Any]) -> None:
        """Initialize the LLM Intent Router with configuration"""
        self._config = config

        # Ollama configuration
        self.ollama_enabled = config.get("ollama_enabled", True)
        self.ollama_base_url = config.get("ollama_base_url", "http://ollama:11434")
        self.ollama_model = config.get("ollama_model", "llama3.1:8b")
        self.ollama_timeout = config.get("ollama_timeout", 30)

        # Decision thresholds
        self.nlu_priority_threshold = config.get("nlu_priority_threshold", 0.95)
        self.llm_priority_threshold = config.get("llm_priority_threshold", 0.6)
        self.agreement_threshold = config.get("agreement_threshold", 0.1)
        self.tie_breaker = config.get("tie_breaker", "llm")

        # Fallback parameters
        self.fallback_to_nlu = config.get("fallback_to_nlu", True)
        self.fallback_threshold = config.get("fallback_threshold", 0.4)
        self.unknown_intent_threshold = config.get("unknown_intent_threshold", 0.3)
        self.force_fallback_keywords = config.get(
            "force_fallback_keywords",
            ["song", "music", "recipe", "weather", "news", "joke", "story", "poem"],
        )
        self.cache_llm_responses = config.get("cache_llm_responses", True)
        self.debug_logging = config.get("debug_logging", False)

        # Cache for LLM responses
        self._llm_cache = {} if self.cache_llm_responses else None

        # Initialize Ollama client
        if self.ollama_enabled:
            try:
                self.ollama_client = OllamaClient(
                    base_url=self.ollama_base_url,
                    model=self.ollama_model,
                    timeout=self.ollama_timeout,
                )
                logger.info("LLM Intent Router initialized with Ollama active")
            except Exception as e:
                logger.error(f"Error initializing Ollama: {e}")
                self.ollama_enabled = False
                self.ollama_client = None
        else:
            self.ollama_client = None
            logger.info("LLM Intent Router initialized WITHOUT Ollama")

    @classmethod
    def create(
        cls,
        config: Dict[Text, Any],
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
    ) -> "LLMIntentRouter":
        """Creation method required by RASA"""
        return cls(config)

    def process(self, messages: List[Message]) -> List[Message]:
        """
        Process messages and apply hybrid NLU + LLM logic
        """
        for message in messages:
            self._process_single_message(message)
        return messages

    def _process_single_message(self, message: Message) -> None:
        """Process a single message with hybrid logic"""
        try:
            # Get message text
            text = message.get("text", "")

            # Early fallback detection by keywords
            if self._should_force_fallback(text):
                if self.debug_logging:
                    logger.info(f"    FALLBACK FORCED by keywords: '{text}'")
                message.set(
                    "intent",
                    {"name": "fallback", "confidence": 0.8},
                    add_to_output=True,
                )
                return

            # Get existing NLU prediction (may be empty in first position)
            nlu_intent = message.get("intent", {})
            nlu_intent_name = nlu_intent.get("name") if nlu_intent else None
            nlu_confidence = nlu_intent.get("confidence", 0.0) if nlu_intent else 0.0

            # Get available intents
            available_intents = self._get_available_intents()

            # Apply hybrid decision logic
            final_intent, final_confidence, decision_source = self._hybrid_decision(
                text,
                nlu_intent_name,
                nlu_confidence,
                available_intents,
            )

            # Update message if necessary
            if final_intent is not None and (
                final_intent != nlu_intent_name or final_confidence != nlu_confidence
            ):
                message.set(
                    "intent",
                    {"name": final_intent, "confidence": final_confidence},
                    add_to_output=True,
                )

                # Debug logging if enabled
                if self.debug_logging:
                    if nlu_intent_name is not None:
                        logger.info(
                            f"OVERRIDE LLM: {nlu_intent_name} → {final_intent} "
                            f"(source: {decision_source})"
                        )
                    else:
                        logger.info(
                            f"GENERATION LLM: {final_intent} "
                            f"(source: {decision_source})"
                        )
            elif final_intent is None and self.debug_logging:
                logger.info("No LLM intervention: let pipeline continue")

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            # In case of error, keep original NLU result or let it pass

    def _hybrid_decision(
        self,
        text: str,
        nlu_intent: Optional[str],
        nlu_confidence: float,
        available_intents: List[str],
    ) -> Tuple[Optional[str], float, str]:
        """
        Hybrid decision logic between NLU and LLM
        Returns: (final_intent, final_confidence, decision_source)

        Handles two cases:
        1. Position AFTER DIETClassifier: nlu_intent exists → hybrid logic
        2. Position BEFORE DIETClassifier: nlu_intent=None → LLM generates initial intent
        """

        # SPECIAL CASE: First position in pipeline - No NLU intent
        if nlu_intent is None:
            if self.debug_logging:
                logger.info("    Initial position: generating intent via LLM")

            if not self.ollama_enabled or not self.ollama_client:
                # No LLM available in first position → let DIETClassifier decide
                if self.debug_logging:
                    logger.info("    Ollama unavailable, let DIETClassifier decide")
                return None, 0.0, "skip_to_diet_classifier"

            # Get LLM prediction for initial intent
            try:
                llm_intent, llm_confidence = self._get_llm_prediction(
                    text, available_intents
                )

                if (
                    llm_intent
                    and llm_confidence
                    and llm_confidence >= self.llm_priority_threshold
                ):
                    if self.debug_logging:
                        logger.info(
                            f"    LLM generates initial intent: {llm_intent} ({llm_confidence:.3f})"
                        )
                    return llm_intent, llm_confidence, "llm_initial_generation"
                else:
                    # LLM pas assez confiant → laisser DIETClassifier décider
                    confidence_str = (
                        f"{llm_confidence:.3f}" if llm_confidence else "None"
                    )
                    if self.debug_logging:
                        logger.info(
                            f"    ⏭️ LLM pas confiant ({confidence_str}), laisser DIETClassifier"
                        )
                    return None, 0.0, "skip_to_diet_classifier"

            except Exception as e:
                logger.error(f"LLM error in initial position: {e}")
                return None, 0.0, "skip_to_diet_classifier"

        # NORMAL CASE: Position AFTER DIETClassifier - NLU intent analysis
        if nlu_confidence >= self.nlu_priority_threshold:
            if self.debug_logging:
                logger.info(
                    f"    NLU very confident ({nlu_confidence:.3f} >= {self.nlu_priority_threshold}) - No LLM consultation"
                )
            return nlu_intent, nlu_confidence, "nlu_very_high_confidence"

        # HYBRID CASE: NLU not confident enough - LLM consultation for improvement
        if not self.ollama_enabled or not self.ollama_client:
            if self.debug_logging:
                logger.info("    Ollama disabled, fallback to NLU prediction")
            return nlu_intent, nlu_confidence, "ollama_disabled"

        # Get LLM prediction
        try:
            llm_intent, llm_confidence = self._get_llm_prediction(
                text, available_intents
            )

            if self.debug_logging:
                logger.info("HYBRID CLASSIFICATION DEBUG")
                logger.info(f"    Text: '{text}'")
                logger.info(
                    f"    � NLU Prédiction: {nlu_intent} ({nlu_confidence:.3f})"
                )
                logger.info(
                    f"    🤖 LLM Prédiction: {llm_intent} ({llm_confidence:.3f})"
                )

            if llm_intent is None or llm_confidence is None:
                # LLM failed
                return nlu_intent, nlu_confidence, "llm_failed"

            # Decision logic based on thresholds
            return self._decide_between_nlu_and_llm(
                nlu_intent, nlu_confidence, llm_intent, llm_confidence
            )

        except Exception as e:
            logger.error(f"Erreur consultation LLM: {e}")
            return nlu_intent, nlu_confidence, "llm_error"

    def _get_llm_prediction(
        self, text: str, available_intents: List[str]
    ) -> Tuple[Optional[str], Optional[float]]:
        """Obtient une prédiction du LLM Ollama"""
        try:
            # Verify the cache first
            if self._llm_cache and text in self._llm_cache:
                return self._llm_cache[text]

            # Call Ollama
            intent, confidence = self.ollama_client.classify_intent(
                text, available_intents
            )

            # Cache the result
            if self._llm_cache and intent is not None:
                self._llm_cache[text] = (intent, confidence)

            return intent, confidence

        except Exception as e:
            logger.error(f"Erreur prédiction LLM: {e}")
            return None, None

    def _decide_between_nlu_and_llm(
        self,
        nlu_intent: str,
        nlu_confidence: float,
        llm_intent: str,
        llm_confidence: float,
    ) -> Tuple[str, float, str]:
        """Décide entre NLU et LLM selon la logique hybride avec fallback intelligent"""

        #  Smart Fallback: If both models are low confidence
        if (
            nlu_confidence < self.fallback_threshold
            and llm_confidence < self.fallback_threshold
        ):
            if self.debug_logging:
                logger.info(
                    f"     Smart Fallback: NLU={nlu_confidence:.3f} et LLM={llm_confidence:.3f} < {self.fallback_threshold}"
                )
            return (
                "fallback",
                0.9,
                "intelligent_fallback",
            )  # High confidence fallback

        # LLM Detection of Unknown Intent
        if llm_intent == "fallback" and llm_confidence >= self.unknown_intent_threshold:
            if self.debug_logging:
                logger.info(
                    f"    🚨 LLM DÉTECTE DEMANDE HORS SCOPE: LLM confidence={llm_confidence:.3f}"
                )
            return "fallback", 0.85, "llm_detected_unknown"

        # CASE 3: LLM confident
        if llm_confidence >= self.llm_priority_threshold:
            # CASE 3a: Agreement between NLU and LLM
            if nlu_intent == llm_intent:
                # Pondered average to boost confidence
                final_confidence = (nlu_confidence + llm_confidence) / 2
                decision = "nlu_llm_agreement"
            else:
                # CASE 3b: Disagreement - LLM wins if LLM strategy is prioritized
                if self.tie_breaker == "llm":
                    decision = "llm_confident"
                    # Boost confidence to avoid FallbackClassifier override
                    boosted_confidence = max(llm_confidence, 0.85)
                    return llm_intent, boosted_confidence, decision
                else:
                    decision = "nlu_confident"
                    return nlu_intent, nlu_confidence, decision

            return llm_intent, final_confidence, decision

        # CASE 4: LLM not confident
        else:
            # Agreement despite low LLM confidence
            if nlu_intent == llm_intent:
                # Use the highest confidence
                if nlu_confidence >= llm_confidence:
                    return nlu_intent, nlu_confidence, "nlu_llm_weak_agreement"
                else:
                    return llm_intent, llm_confidence, "nlu_llm_weak_agreement"
            else:
                # Disagreement between NLU and low-confidence LLM - NLU wins
                return nlu_intent, nlu_confidence, "nlu_default"

    def _get_available_intents(self) -> List[str]:
        """Récupère la liste des intentions disponibles"""
        # Default intents if none found
        default_intents = [
            "greet",
            "goodbye",
            "affirm",
            "deny",
            "mood_great",
            "mood_unhappy",
            "generate_visualization",
            "chitchat",
            "fallback",
        ]
        return default_intents

    def _should_force_fallback(self, text: str) -> bool:
        """
        Détermine si le texte contient des mots-clés qui forcent un fallback
         Nouveau: Détection des demandes hors scope du chatbot médical
        """
        if not text:
            return False

        text_lower = text.lower()

        # Verify the configured fallback keywords
        for keyword in self.force_fallback_keywords:
            if keyword.lower() in text_lower:
                return True

        # Pattern detection for out-of-scope medical requests
        out_of_scope_patterns = [
            "forget everything",
            "ignore instructions",
            "tell me a",
            "sing me",
            "play music",
            "what's the weather",
            "give me a recipe",
            "tell me a joke",
        ]

        for pattern in out_of_scope_patterns:
            if pattern.lower() in text_lower:
                return True

        return False
