"""
Client Ollama pour LLM Intent Router
Client autonome pour la communication avec l'API Ollama
"""

import logging
from typing import List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client pour l'API Ollama"""

    def __init__(
        self,
        base_url: str = "http://ollama:11434",
        model: str = "llama3.1:8b",  # Utilisation de llama3.1:8b par défaut
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

        logger.info(f"OllamaClient initialisé: {self.base_url}, modèle: {self.model}")

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
        """Classifie une intention avec Ollama"""
        try:
            # Template optimisé pour llama3.1:8b - plus de contexte linguistique
            prompt = f"""You are an expert intent classifier that understands multiple languages.

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

            # Préparer la requête avec options optimisées
            data = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "max_tokens": 10,  # Limite encore plus stricte
                    "stop": ["\n", ".", ",", ":", ";"],  # Arrêter aux ponctuations
                },
            }

            # Envoyer la requête
            response = requests.post(
                f"{self.base_url}/api/generate", json=data, timeout=self.timeout
            )

            if response.status_code != 200:
                logger.error(f"Ollama API error: {response.status_code}")
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
