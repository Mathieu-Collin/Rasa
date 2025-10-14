"""
LLM Intent Router - Composant hybride pour RASA
Combine les predictions NLU traditionnelles avec un LLM Ollama
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Text, Tuple

import yaml
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
    pour ameliorer la precision de detection d'intentions
    """

    def __init__(self, config: Dict[Text, Any]) -> None:
        """Initialise le LLM Intent Router avec la configuration"""
        self._config = config

        # Configuration Ollama
        self._ollama_enabled = config.get("ollama_enabled", True)
        # Configuration Ollama - URL depuis la config ou variables d'environnement
        self._ollama_base_url = config.get("ollama_base_url", "http://ollama:11434")
        self._ollama_model = config.get("ollama_model", "llama3.2:1b")
        self._ollama_timeout = config.get("ollama_timeout", 30)

        # Configuration des seuils de decision hybride (LLM PRIORITAIRE)
        # Seuil NLU plus élevé pour privilégier le LLM
        self._nlu_priority_threshold = config.get("nlu_priority_threshold", 0.95)
        self._llm_priority_threshold = config.get("llm_priority_threshold", 0.7)
        self._agreement_threshold = config.get("agreement_threshold", 0.1)
        self._fallback_to_nlu = config.get("fallback_to_nlu", True)
        # Nouveau: Configurateur de tie-breaker (par défaut LLM prioritaire)
        self._tie_breaker = config.get("tie_breaker", "llm")

        # Configuration du comportement
        self._parallel_processing = config.get("parallel_processing", False)
        self._cache_llm_responses = config.get("cache_llm_responses", True)
        self._debug_logging = config.get("debug_logging", False)

        # Initialisation du client Ollama
        self._ollama_client = None
        if self._ollama_enabled:
            try:
                self._ollama_client = OllamaClient(
                    base_url=self._ollama_base_url,
                    model=self._ollama_model,
                    timeout=self._ollama_timeout,
                )

                # Test de sante initial
                if not self._ollama_client.health_check():
                    logger.warning("Ollama non disponible, fallback vers NLU seul")
                    self._ollama_enabled = False
                else:
                    logger.info("LLM Intent Router initialise avec Ollama actif")

            except Exception as e:
                logger.error(f"Erreur initialisation Ollama: {e}")
                self._ollama_enabled = False

        # Cache pour les reponses LLM
        self._llm_cache: Dict[str, Tuple[str, float]] = {}

        # Statistiques
        self._stats = {
            "total_messages": 0,
            "nlu_decisions": 0,
            "llm_decisions": 0,
            "agreement_cases": 0,
            "disagreement_cases": 0,
            "ollama_errors": 0,
            "cache_hits": 0,
        }

        if self._debug_logging:
            logger.info(
                f"LLMIntentRouter config: NLU_threshold={self._nlu_priority_threshold}, "
                f"LLM_threshold={self._llm_priority_threshold}, "
                f"agreement_threshold={self._agreement_threshold}"
            )

    @classmethod
    def create(
        cls,
        config: Dict[Text, Any],
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
    ) -> "LLMIntentRouter":
        """Factory method pour creer une instance du composant"""
        return cls(config)

    def process(self, messages: List[Message]) -> List[Message]:
        """
        Traite les messages avec la logique hybride NLU + LLM

        Args:
            messages: Liste des messages a traiter

        Returns:
            Messages avec intentions mises a jour par la logique hybride
        """
        for message in messages:
            try:
                self._stats["total_messages"] += 1

                # Recuperer la prediction NLU existante
                nlu_intent = message.get("intent", {}).get("name")
                nlu_confidence = message.get("intent", {}).get("confidence", 0.0)

                if not nlu_intent:
                    if self._debug_logging:
                        logger.warning("Aucune intention NLU trouvee, skip du message")
                    continue

                # Appliquer la logique hybride
                final_intent, final_confidence, decision_source = self._hybrid_classify(
                    message.get("text", ""), nlu_intent, nlu_confidence
                )

                # Mettre a jour le message avec la decision finale
                message.set(
                    "intent", {"name": final_intent, "confidence": final_confidence}
                )

                # Ajouter des metadonnees sur la decision
                message.set(
                    "llm_router_metadata",
                    {
                        "original_nlu_intent": nlu_intent,
                        "original_nlu_confidence": nlu_confidence,
                        "final_intent": final_intent,
                        "final_confidence": final_confidence,
                        "decision_source": decision_source,
                        "ollama_enabled": self._ollama_enabled,
                    },
                )

                if self._debug_logging:
                    logger.info("═" * 80)
                    logger.info("📋 RÉSUMÉ DÉCISION FINALE (LLM PRIORITAIRE)")
                    logger.info(
                        f"   📝 Message: '{message.get('text', '')[:50]}{'...' if len(message.get('text', '')) > 50 else ''}'"
                    )
                    logger.info(
                        f"   🧠 NLU Original: {nlu_intent} (confiance: {nlu_confidence:.3f})"
                    )
                    logger.info(
                        f"   🏆 Décision Finale: {final_intent} (confiance: {final_confidence:.3f})"
                    )
                    logger.info(f"   🎯 Source: {decision_source}")
                    logger.info(
                        f"   ⚙️  Stratégie: LLM prioritaire (tie_breaker: {self._tie_breaker})"
                    )

                    # Indicateur de changement
                    if (
                        final_intent != nlu_intent
                        or abs(final_confidence - nlu_confidence) > 0.05
                    ):
                        logger.info(
                            "   🔄 CHANGEMENT: Intent ou confiance modifiés par le routeur hybride LLM-prioritaire"
                        )
                        if final_intent != nlu_intent:
                            logger.info(
                                f"   🎯 OVERRIDE LLM: {nlu_intent} → {final_intent}"
                            )
                    else:
                        logger.info("   ✓ MAINTENU: Décision NLU conservée")

                    logger.info("═" * 80)

            except Exception as e:
                logger.error(f"Erreur traitement message: {e}")
                # En cas d'erreur, garder la prediction NLU originale
                continue

        return messages

    def _hybrid_classify(
        self, text: str, nlu_intent: str, nlu_confidence: float
    ) -> Tuple[str, float, str]:
        """
        Logique principale de classification hybride

        Args:
            text: Texte du message utilisateur
            nlu_intent: Intention predite par NLU
            nlu_confidence: Confiance de la prediction NLU

        Returns:
            Tuple (intention_finale, confiance_finale, source_decision)
        """

        # 🎯 DEBUG: Affichage des données d'entrée
        if self._debug_logging:
            logger.info("🎯 HYBRID CLASSIFICATION DEBUG (LLM PRIORITAIRE)")
            logger.info(f"   📝 Texte: '{text}'")
            logger.info(
                f"   🧠 NLU Prédiction: {nlu_intent} (confiance: {nlu_confidence:.3f})"
            )
            logger.info(
                f"   ⚙️  Seuils: NLU={self._nlu_priority_threshold}, LLM={self._llm_priority_threshold}, Accord={self._agreement_threshold}"
            )
            logger.info(f"   🏆 Tie-Breaker: {self._tie_breaker}")

        # Cas 1: NLU TRÈS confiant (seuil élevé 0.95+), pas besoin du LLM
        if nlu_confidence >= self._nlu_priority_threshold:
            self._stats["nlu_decisions"] += 1
            if self._debug_logging:
                logger.info(
                    f"   ✅ DÉCISION: NLU TRÈS haute confiance ({nlu_confidence:.3f} >= {self._nlu_priority_threshold})"
                )
                logger.info(
                    f"   🏆 RÉSULTAT: {nlu_intent} (source: nlu_very_high_confidence)"
                )
            return nlu_intent, nlu_confidence, "nlu_very_high_confidence"

        # Cas 2: Ollama desactive ou indisponible, utiliser NLU
        if not self._ollama_enabled or not self._ollama_client:
            self._stats["nlu_decisions"] += 1
            if self._debug_logging:
                logger.info("   ⚠️  DÉCISION: Ollama indisponible, fallback NLU")
                logger.info(f"   🏆 RÉSULTAT: {nlu_intent} (source: nlu_fallback)")
            return nlu_intent, nlu_confidence, "nlu_fallback"

        # Cas 3: Obtenir la prediction LLM
        try:
            if self._debug_logging:
                logger.info("   🤖 Consultation du LLM Ollama...")

            llm_intent, llm_confidence = self._get_llm_prediction(text)

            if self._debug_logging:
                logger.info(
                    f"   🤖 LLM Prédiction: {llm_intent} (confiance: {llm_confidence:.3f})"
                )
                logger.info(
                    f"   ⚖️  Comparaison: NLU='{nlu_intent}' vs LLM='{llm_intent}'"
                )
                logger.info(
                    f"   📊 Écart confiance: {abs(nlu_confidence - llm_confidence):.3f}"
                )

            # Cas 3a: LLM confiant (seuil abaissé à 0.7) - PRIORITÉ LLM
            if llm_confidence >= self._llm_priority_threshold:
                self._stats["llm_decisions"] += 1
                if llm_intent != nlu_intent:
                    self._stats["disagreement_cases"] += 1
                else:
                    self._stats["agreement_cases"] += 1
                if self._debug_logging:
                    agreement_status = (
                        "accord" if llm_intent == nlu_intent else "désaccord"
                    )
                    logger.info(
                        f"   ✅ DÉCISION: LLM confiant ({llm_confidence:.3f} >= {self._llm_priority_threshold}) - {agreement_status}"
                    )
                    logger.info(f"   🏆 RÉSULTAT: {llm_intent} (source: llm_confident)")
                return llm_intent, llm_confidence, "llm_confident"

            # Cas 3b: Accord entre NLU et LLM (intentions identiques)
            if llm_intent == nlu_intent:
                self._stats["agreement_cases"] += 1

                # CHANGEMENT MAJEUR: En cas d'accord, privilégier le LLM par défaut
                if self._tie_breaker == "llm" or llm_confidence >= nlu_confidence:
                    if self._debug_logging:
                        logger.info(
                            f"   ✅ DÉCISION: Accord intentions (tie-breaker: {self._tie_breaker}), LLM choisi"
                        )
                        logger.info(
                            f"   🏆 RÉSULTAT: {llm_intent} (source: llm_agreement)"
                        )
                    return llm_intent, llm_confidence, "llm_agreement"
                else:
                    if self._debug_logging:
                        logger.info(
                            f"   ✅ DÉCISION: Accord intentions (tie-breaker: {self._tie_breaker}), NLU choisi"
                        )
                        logger.info(
                            f"   🏆 RÉSULTAT: {nlu_intent} (source: nlu_agreement)"
                        )
                    return nlu_intent, nlu_confidence, "nlu_agreement"

            # Cas 3c: Confidences proches (dans le seuil d'accord)
            elif abs(nlu_confidence - llm_confidence) <= self._agreement_threshold:
                self._stats["agreement_cases"] += 1

                # CHANGEMENT MAJEUR: En cas de confidences proches, privilégier le LLM par défaut
                if self._tie_breaker == "llm":
                    if self._debug_logging:
                        logger.info(
                            f"   ✅ DÉCISION: Confidences proches (écart: {abs(nlu_confidence - llm_confidence):.3f}), LLM prioritaire"
                        )
                        logger.info(
                            f"   🏆 RÉSULTAT: {llm_intent} (source: llm_close_confidence)"
                        )
                    return llm_intent, llm_confidence, "llm_close_confidence"
                else:
                    # Utiliser la confiance la plus élevée si tie_breaker != "llm"
                    if llm_confidence > nlu_confidence:
                        if self._debug_logging:
                            logger.info(
                                "   ✅ DÉCISION: Confidences proches, LLM plus confiant"
                            )
                            logger.info(
                                f"   🏆 RÉSULTAT: {llm_intent} (source: llm_higher_confidence)"
                            )
                        return llm_intent, llm_confidence, "llm_higher_confidence"
                    else:
                        if self._debug_logging:
                            logger.info(
                                "   ✅ DÉCISION: Confidences proches, NLU plus confiant"
                            )
                            logger.info(
                                f"   🏆 RÉSULTAT: {nlu_intent} (source: nlu_higher_confidence)"
                            )
                        return nlu_intent, nlu_confidence, "nlu_higher_confidence"

            # Cas 3d: Désaccord net - utiliser la confiance la plus élevée (mais privilégier LLM si égalité)
            else:
                self._stats["disagreement_cases"] += 1
                if llm_confidence > nlu_confidence:
                    self._stats["llm_decisions"] += 1
                    if self._debug_logging:
                        logger.info(
                            f"   ⚔️  DÉCISION: Désaccord net, LLM plus confiant ({llm_confidence:.3f} > {nlu_confidence:.3f})"
                        )
                        logger.info(
                            f"   🏆 RÉSULTAT: {llm_intent} (source: llm_disagreement)"
                        )
                    return llm_intent, llm_confidence, "llm_disagreement"
                elif nlu_confidence > llm_confidence:
                    self._stats["nlu_decisions"] += 1
                    if self._debug_logging:
                        logger.info(
                            f"   ⚔️  DÉCISION: Désaccord net, NLU plus confiant ({nlu_confidence:.3f} > {llm_confidence:.3f})"
                        )
                        logger.info(
                            f"   🏆 RÉSULTAT: {nlu_intent} (source: nlu_disagreement)"
                        )
                    return nlu_intent, nlu_confidence, "nlu_disagreement"
                else:
                    # Égalité parfaite de confiance : privilégier LLM par défaut
                    self._stats["llm_decisions"] += 1
                    if self._debug_logging:
                        logger.info(
                            f"   ⚔️  DÉCISION: Égalité confiance ({llm_confidence:.3f} = {nlu_confidence:.3f}), LLM prioritaire"
                        )
                        logger.info(
                            f"   🏆 RÉSULTAT: {llm_intent} (source: llm_tie_breaker)"
                        )
                    return llm_intent, llm_confidence, "llm_tie_breaker"

        except Exception as e:
            logger.error(f"Erreur prediction LLM: {e}")
            self._stats["ollama_errors"] += 1

            # Fallback vers NLU en cas d'erreur
            if self._fallback_to_nlu:
                self._stats["nlu_decisions"] += 1
                if self._debug_logging:
                    logger.info("   ❌ DÉCISION: Erreur LLM, fallback vers NLU")
                    logger.info(
                        f"   🏆 RÉSULTAT: {nlu_intent} (source: nlu_error_fallback)"
                    )
                return nlu_intent, nlu_confidence, "nlu_error_fallback"
            else:
                # Retourner une intention fallback avec confiance faible
                if self._debug_logging:
                    logger.info("   ❌ DÉCISION: Erreur LLM, intention fallback")
                    logger.info("   🏆 RÉSULTAT: fallback (source: error_fallback)")
                return "fallback", 0.1, "error_fallback"

    def _get_llm_prediction(self, text: str) -> Tuple[str, float]:
        """
        Obtient la prediction du LLM avec cache

        Args:
            text: Texte a classifier

        Returns:
            Tuple (intention, confiance)
        """
        # Verification du cache
        if self._cache_llm_responses and text in self._llm_cache:
            self._stats["cache_hits"] += 1
            if self._debug_logging:
                logger.debug(f"Cache hit pour: '{text[:30]}...'")
            return self._llm_cache[text]

        # Charger les intentions disponibles depuis la config
        available_intents = self._get_available_intents()

        # Appel au LLM avec template par défaut
        prompt_template = """You are an intent classifier for a conversational AI system.

Analyze the following user message and classify it into one of the available intents.

Available intents: [{available_intents}]

User message: "{user_message}"

Instructions:
1. Choose the most appropriate intent from the available list
2. If no intent matches well, choose the closest one
3. Provide a confidence score between 0.0 and 1.0
4. Be consistent with your classifications

Respond in this exact format:
Intent: <intent_name>
Confidence: <score>
"""

        intent, confidence = self._ollama_client.classify_intent(
            text, available_intents
        )

        # Mise en cache
        if self._cache_llm_responses:
            self._llm_cache[text] = (intent, confidence)

            # Limiter la taille du cache
            if len(self._llm_cache) > 1000:
                # Supprimer les plus anciens (FIFO simple)
                oldest_keys = list(self._llm_cache.keys())[:100]
                for key in oldest_keys:
                    del self._llm_cache[key]

        return intent, confidence

    def _get_available_intents(self) -> List[str]:
        """
        Recupere la liste des intentions disponibles depuis la configuration

        Returns:
            Liste des intentions supportees
        """
        try:
            # Essayer de charger depuis ollama_config.yml
            config_path = Path("/workspace/src/config/ollama_config.yml")
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)

                intents = config.get("intents", {}).get("supported_intents", [])
                if intents:
                    return intents

        except Exception as e:
            logger.warning(
                f"Impossible de charger les intentions depuis la config: {e}"
            )

        # Fallback vers une liste par defaut
        return [
            "greet",
            "goodbye",
            "affirm",
            "deny",
            "question",
            "request",
            "command",
            "chitchat",
            "fallback",
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du composant"""
        stats = self._stats.copy()

        # Ajouter des metriques calculees
        total = stats["total_messages"]
        if total > 0:
            stats["nlu_decision_rate"] = stats["nlu_decisions"] / total
            stats["llm_decision_rate"] = stats["llm_decisions"] / total
            stats["agreement_rate"] = stats["agreement_cases"] / total
            stats["disagreement_rate"] = stats["disagreement_cases"] / total
            stats["error_rate"] = stats["ollama_errors"] / total
            stats["cache_hit_rate"] = (
                stats["cache_hits"] / total if stats["cache_hits"] > 0 else 0.0
            )

        # Ajouter les stats du client Ollama si disponible
        if self._ollama_client:
            ollama_stats = self._ollama_client.get_stats()
            stats["ollama_stats"] = ollama_stats

        return stats

    def reset_stats(self) -> None:
        """Remet a zero les statistiques"""
        self._stats = {
            "total_messages": 0,
            "nlu_decisions": 0,
            "llm_decisions": 0,
            "agreement_cases": 0,
            "disagreement_cases": 0,
            "ollama_errors": 0,
            "cache_hits": 0,
        }

        if self._ollama_client:
            self._ollama_client.reset_stats()

        self._llm_cache.clear()

    def __repr__(self) -> str:
        return (
            f"<LLMIntentRouter ollama_enabled={self._ollama_enabled}, "
            f"nlu_threshold={self._nlu_priority_threshold}, "
            f"llm_threshold={self._llm_priority_threshold}>"
        )
