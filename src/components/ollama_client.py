"""
Client Ollama pour LLM Intent Router
Client autonome pour la communication avec l'API Ollama
Support de la configuration centralisée et variables d'environnement
"""

import logging
from typing import List, Optional, Tuple

import requests

# Import du gestionnaire de configuration centralisée
try:
    from src.config.llm_config_manager import get_llm_config_manager
except ImportError:
    # Fallback si le module n'est pas accessible
    get_llm_config_manager = None

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client pour l'API Ollama avec configuration centralisée"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        use_centralized_config: bool = True,
    ):
        """
        Initialise le client Ollama

        Args:
            base_url: URL Ollama (override la config centralisée si fournie)
            model: Modèle à utiliser (override la config centralisée si fournie)
            timeout: Timeout en secondes (override la config centralisée si fournie)
            use_centralized_config: Utiliser la configuration centralisée
        """
        # Charger la configuration centralisée si disponible et demandée
        if use_centralized_config and get_llm_config_manager:
            try:
                config_manager = get_llm_config_manager()
                client_config = config_manager.get_effective_model_for_ollama_client()

                # Utiliser les valeurs de la config centralisée sauf si overridées
                self.base_url = (base_url or client_config["base_url"]).rstrip("/")
                self.model = model or client_config["model"]
                self.timeout = timeout or client_config["timeout"]
                self.max_retries = client_config.get("max_retries", 3)
                self.fallback_models = client_config.get("fallback_models", [])
                self.model_config = client_config.get("model_config", {})

                logger.info(f"Configuration centralisée chargée - Modèle: {self.model}")

            except Exception as e:
                logger.warning(
                    f"Erreur chargement config centralisée: {e}, utilisation valeurs par défaut"
                )
                self._set_default_values(base_url, model, timeout)
        else:
            # Configuration manuelle ou fallback
            self._set_default_values(base_url, model, timeout)

        logger.info(f"OllamaClient initialisé: {self.base_url}, modèle: {self.model}")

    def _set_default_values(
        self, base_url: Optional[str], model: Optional[str], timeout: Optional[int]
    ):
        """Définit les valeurs par défaut"""
        self.base_url = (base_url or "http://ollama:11434").rstrip("/")
        self.model = model or "llama3.1:8b"
        self.timeout = timeout or 30
        self.max_retries = 3
        self.fallback_models = ["llama3.1:8b", "tinyllama"]
        self.model_config = {
            "temperature": 0.1,
            "num_predict": 10,  # Ollama utilise num_predict au lieu de max_tokens
            "stop_sequences": ["\n", ".", ",", ":", ";"],
        }

    def health_check(self) -> bool:
        """Vérifie si Ollama est accessible"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    def classify_intent(
        self, user_message: str, available_intents: List[str]
    ) -> Tuple[Optional[str], Optional[float]]:
        """Classifie une intention avec Ollama en utilisant la configuration centralisée"""
        try:
            # Obtenir le template de prompt depuis la configuration
            prompt = self._get_optimized_prompt(user_message, available_intents)

            # Préparer les options du modèle depuis la configuration
            model_options = {
                "temperature": self.model_config.get("temperature", 0.1),
                "num_predict": self.model_config.get(
                    "num_predict", 10
                ),  # Ollama utilise num_predict
                "stop": self.model_config.get(
                    "stop_sequences", ["\n", ".", ",", ":", ";"]
                ),
            }

            # Préparer la requête
            data = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": model_options,
            }

            # Envoyer la requête avec retry si configured
            response = self._send_request_with_retry(data)

            if not response:
                return None, 0.0

            result = response.json()
            llm_response = result.get("response", "").strip()

            # Parser la réponse
            intent, confidence = self._parse_simple_response(
                llm_response, available_intents
            )

            if intent and confidence is not None:
                logger.debug(f"Classification réussie: {intent} ({confidence})")
                return intent, confidence
            else:
                logger.warning(f"Impossible de parser la réponse: '{llm_response}'")
                return None, 0.0

        except Exception as e:
            logger.error(f"Erreur classification Ollama: {e}")
            return None, 0.0

    def _get_optimized_prompt(
        self, user_message: str, available_intents: List[str]
    ) -> str:
        """Génère un prompt optimisé selon la configuration du modèle"""
        # Obtenir le template depuis la configuration centralisée
        if get_llm_config_manager:
            try:
                config_manager = get_llm_config_manager()
                template_name = self.model_config.get(
                    "prompt_template", "optimized_multilingual"
                )
                template = config_manager.get_prompt_template(template_name)

                return template.format(
                    user_message=user_message,
                    available_intents=", ".join(available_intents),
                )
            except Exception as e:
                logger.warning(f"Erreur récupération template: {e}")

        # Template par défaut si problème avec la configuration
        return f"""You are an expert intent classifier that understands multiple languages.

Task: Classify the user message into ONE of the given categories.
Message: "{user_message}"
Available categories: {", ".join(available_intents)}

Rules:
- Respond with ONLY the category name
- Understand French, English, and other languages
- "Bonjour", "Salut", "Hello", "Hi" → greet
- "Au revoir", "Goodbye", "Bye" → goodbye
- No explanation needed

Classification:"""

    def _send_request_with_retry(self, data) -> Optional[requests.Response]:
        """Envoie la requête avec retry selon la configuration"""
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/api/generate", json=data, timeout=self.timeout
                )

                if response.status_code == 200:
                    return response
                else:
                    logger.warning(
                        f"Tentative {attempt + 1}: Status {response.status_code}"
                    )

            except Exception as e:
                logger.warning(f"Tentative {attempt + 1} échouée: {e}")

            # Attendre avant retry (sauf dernière tentative)
            if attempt < self.max_retries - 1:
                import time

                time.sleep(1.0)

        logger.error(f"Tous les {self.max_retries} essais ont échoué")
        return None

    def _parse_simple_response(
        self, llm_response: str, available_intents: List[str]
    ) -> Tuple[Optional[str], Optional[float]]:
        """Parse la réponse par exemples du LLM pour extraire intention"""
        try:
            # Nettoyer la réponse
            response = llm_response.strip().lower()

            # Format attendu: "-> intent" ou juste "intent"
            if response.startswith("->"):
                response = response[2:].strip()

            # Chercher l'intent exact dans la réponse
            for intent in available_intents:
                if intent.lower() == response or response.startswith(intent.lower()):
                    return intent, 0.8

            # Si aucun intent trouvé, essayer de parser les mots
            words = response.split()
            if words:
                first_word = words[0].strip(',:."')
                for intent in available_intents:
                    if intent.lower() == first_word:
                        return intent, 0.8

            # Fallback si rien trouvé
            logger.debug(f"Aucun intent trouvé dans: '{response}'")
            return None, None

        except Exception as e:
            logger.error(f"Erreur parsing réponse: {e}")
            return None, None
