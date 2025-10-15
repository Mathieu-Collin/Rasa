"""
LLM Intent Router - Composant hybride pour RASA
Combine les predictions NLU traditionnelles avec un LLM Ollama
Version simplifiée sans configuration centralisée
"""

import logging
from typing import Any, Dict, List, Optional, Text, Tuple

from rasa.engine.graph import ExecutionContext, GraphComponent
from rasa.engine.recipes.default_recipe import DefaultV1Recipe
from rasa.engine.storage.resource import Resource
from rasa.engine.storage.storage import ModelStorage
from rasa.shared.nlu.training_data.message import Message

# Import du client Ollama
from .ollama_client import OllamaClient

logger = logging.getLogger(__name__)


@DefaultV1Recipe.register(
    DefaultV1Recipe.ComponentType.INTENT_CLASSIFIER, is_trainable=False
)
class LLMIntentRouter(GraphComponent):
    """
    Composant hybride qui combine les classifications NLU RASA avec un LLM Ollama
    pour améliorer la precision de detection d'intentions
    """

    def __init__(self, config: Dict[Text, Any]) -> None:
        """Initialise le LLM Intent Router avec configuration simple"""
        self._config = config

        # Configuration Ollama simple
        self.ollama_enabled = config.get("ollama_enabled", True)
        self.ollama_base_url = config.get("ollama_base_url", "http://ollama:11434")
        self.ollama_model = config.get("ollama_model", "llama3.1:8b")
        self.ollama_timeout = config.get("ollama_timeout", 30)

        # Seuils de décision
        self.nlu_priority_threshold = config.get("nlu_priority_threshold", 0.95)
        self.llm_priority_threshold = config.get("llm_priority_threshold", 0.7)
        self.agreement_threshold = config.get("agreement_threshold", 0.1)
        self.tie_breaker = config.get("tie_breaker", "llm")

        # Options
        self.fallback_to_nlu = config.get("fallback_to_nlu", True)
        self.cache_llm_responses = config.get("cache_llm_responses", True)
        self.debug_logging = config.get("debug_logging", False)

        # Cache pour les réponses LLM
        self._llm_cache = {} if self.cache_llm_responses else None

        # Initialisation du client Ollama
        if self.ollama_enabled:
            try:
                self.ollama_client = OllamaClient(
                    base_url=self.ollama_base_url,
                    model=self.ollama_model,
                    timeout=self.ollama_timeout,
                )
                logger.info("LLM Intent Router initialise avec Ollama actif")
            except Exception as e:
                logger.error(f"Erreur initialisation Ollama: {e}")
                self.ollama_enabled = False
                self.ollama_client = None
        else:
            self.ollama_client = None
            logger.info("LLM Intent Router initialise SANS Ollama")

    @classmethod
    def create(
        cls,
        config: Dict[Text, Any],
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
    ) -> "LLMIntentRouter":
        """Méthode de création requise par RASA"""
        return cls(config)

    def process(self, messages: List[Message]) -> List[Message]:
        """
        Traite les messages et applique la logique hybride NLU + LLM
        """
        for message in messages:
            self._process_single_message(message)
        return messages

    def _process_single_message(self, message: Message) -> None:
        """Traite un message unique avec la logique hybride"""
        try:
            # Récupérer la prédiction NLU existante (peut être vide en première position)
            nlu_intent = message.get("intent", {})
            nlu_intent_name = nlu_intent.get("name") if nlu_intent else None
            nlu_confidence = nlu_intent.get("confidence", 0.0) if nlu_intent else 0.0

            # Récupérer les intentions disponibles
            available_intents = self._get_available_intents()

            # Appliquer la logique de décision hybride
            final_intent, final_confidence, decision_source = self._hybrid_decision(
                message.get("text", ""),
                nlu_intent_name,
                nlu_confidence,
                available_intents,
            )

            # Mettre à jour le message si nécessaire
            if final_intent is not None and (
                final_intent != nlu_intent_name or final_confidence != nlu_confidence
            ):
                message.set(
                    "intent",
                    {"name": final_intent, "confidence": final_confidence},
                    add_to_output=True,
                )

                # Log debug si activé
                if self.debug_logging:
                    if nlu_intent_name is not None:
                        logger.info(
                            f"🎯 OVERRIDE LLM: {nlu_intent_name} → {final_intent} "
                            f"(source: {decision_source})"
                        )
                    else:
                        logger.info(
                            f"🎯 GÉNÉRATION LLM: {final_intent} "
                            f"(source: {decision_source})"
                        )
            elif final_intent is None and self.debug_logging:
                logger.info("⏭️ Pas d'intervention LLM: laisser pipeline continuer")

        except Exception as e:
            logger.error(f"Erreur traitement message: {e}")
            # En cas d'erreur, on garde le résultat NLU original ou on laisse passer

    def _hybrid_decision(
        self,
        text: str,
        nlu_intent: Optional[str],
        nlu_confidence: float,
        available_intents: List[str],
    ) -> Tuple[Optional[str], float, str]:
        """
        Logique de décision hybride entre NLU et LLM
        Retourne: (intent_final, confidence_finale, source_decision)

        Gère deux cas :
        1. Position APRÈS DIETClassifier : nlu_intent existe → logique hybride
        2. Position AVANT DIETClassifier : nlu_intent=None → LLM génère intention initiale
        """

        # CAS SPÉCIAL: Première position dans le pipeline - Pas d'intention NLU
        if nlu_intent is None:
            if self.debug_logging:
                logger.info("    🚀 Position initiale: génération intention par LLM")

            if not self.ollama_enabled or not self.ollama_client:
                # Pas de LLM disponible en première position → laisser passer au DIETClassifier
                if self.debug_logging:
                    logger.info(
                        "    ⏭️ Ollama indisponible, laisser DIETClassifier décider"
                    )
                return None, 0.0, "skip_to_diet_classifier"

            # Obtenir prédiction LLM pour intention initiale
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
                            f"    🎯 LLM génère intention initiale: {llm_intent} ({llm_confidence:.3f})"
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
                logger.error(f"Erreur LLM en position initiale: {e}")
                return None, 0.0, "skip_to_diet_classifier"

        # CAS NORMAL: Position APRÈS DIETClassifier - Analyse de l'intention NLU
        if nlu_confidence >= self.nlu_priority_threshold:
            if self.debug_logging:
                logger.info(
                    f"    ✅ NLU très confiant ({nlu_confidence:.3f} >= {self.nlu_priority_threshold}) - Pas de consultation LLM"
                )
            return nlu_intent, nlu_confidence, "nlu_very_high_confidence"

        # CAS HYBRIDE: NLU pas assez confiant - Consultation LLM pour amélioration
        if not self.ollama_enabled or not self.ollama_client:
            if self.debug_logging:
                logger.info("    ❌ Ollama désactivé, fallback vers prédiction NLU")
            return nlu_intent, nlu_confidence, "nlu_fallback"
            return nlu_intent, nlu_confidence, "ollama_disabled"

        # Obtenir prédiction LLM
        try:
            llm_intent, llm_confidence = self._get_llm_prediction(
                text, available_intents
            )

            if self.debug_logging:
                logger.info("🎯 HYBRID CLASSIFICATION DEBUG")
                logger.info(f"    📝 Texte: '{text}'")
                logger.info(
                    f"    � NLU Prédiction: {nlu_intent} ({nlu_confidence:.3f})"
                )
                logger.info(
                    f"    🤖 LLM Prédiction: {llm_intent} ({llm_confidence:.3f})"
                )

            if llm_intent is None or llm_confidence is None:
                # LLM failed
                return nlu_intent, nlu_confidence, "llm_failed"

            # Logique de décision selon les seuils
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
            # Vérifier le cache d'abord
            if self._llm_cache and text in self._llm_cache:
                return self._llm_cache[text]

            # Appeler Ollama
            intent, confidence = self.ollama_client.classify_intent(
                text, available_intents
            )

            # Mettre en cache le résultat
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
        """Décide entre NLU et LLM selon la logique hybride"""

        # CAS 3: LLM confiant
        if llm_confidence >= self.llm_priority_threshold:
            # CAS 3a: Accord entre NLU et LLM
            if nlu_intent == llm_intent:
                # Moyenne pondérée pour renforcer la confiance
                final_confidence = (nlu_confidence + llm_confidence) / 2
                decision = "nlu_llm_agreement"
            else:
                # CAS 3b: Désaccord - LLM gagne si stratégie LLM prioritaire
                if self.tie_breaker == "llm":
                    decision = "llm_confident"
                    # Boost confiance pour éviter FallbackClassifier override
                    boosted_confidence = max(llm_confidence, 0.85)
                    return llm_intent, boosted_confidence, decision
                else:
                    decision = "nlu_confident"
                    return nlu_intent, nlu_confidence, decision

            return llm_intent, final_confidence, decision

        # CAS 4: LLM pas confiant
        else:
            # Accord malgré faible confiance LLM
            if nlu_intent == llm_intent:
                # Utiliser la confiance la plus élevée
                if nlu_confidence >= llm_confidence:
                    return nlu_intent, nlu_confidence, "nlu_llm_weak_agreement"
                else:
                    return llm_intent, llm_confidence, "nlu_llm_weak_agreement"
            else:
                # Désaccord + LLM pas confiant - NLU gagne
                return nlu_intent, nlu_confidence, "nlu_default"

    def _get_available_intents(self) -> List[str]:
        """Récupère la liste des intentions disponibles"""
        # Intents par défaut - peut être étendu si nécessaire
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
