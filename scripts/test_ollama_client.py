#!/usr/bin/env python3
"""
Test du client Ollama avec intégration complète
Phase 1.2 du plan d'action LLM Intent Router
"""

import logging
import time
from typing import Dict, List, Optional, Tuple

import requests

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OllamaClient:
    """Client pour communication avec Ollama LLM"""

    def __init__(
        self,
        base_url: str = "http://172.22.0.2:11434",  # IP du bridge réseau par défaut
        model: str = "llama3.2:1b",
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.session = requests.Session()
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_response_time": 0.0,
            "avg_response_time": 0.0,
        }
        logger.info(f"OllamaClient initialisé: {base_url}, modèle: {model}")

    def health_check(self) -> bool:
        """Vérifie la disponibilité du service Ollama"""
        try:
            start_time = time.time()
            response = self.session.get(f"{self.base_url}/", timeout=self.timeout)
            response_time = time.time() - start_time
            self._update_stats(response_time, response.status_code == 200)

            if response.status_code == 200:
                logger.debug(f"Health check OK en {response_time:.3f}s")
                return True
            else:
                logger.warning(f"Health check échec: HTTP {response.status_code}")
                return False
        except requests.RequestException as e:
            logger.error(f"Health check erreur: {e}")
            self._update_stats(0, False)
            return False

    def send_prompt(self, prompt: str, model: Optional[str] = None, **kwargs) -> str:
        """Envoie un prompt générique à Ollama"""
        model_name = model or self.model
        payload = {"model": model_name, "prompt": prompt, "stream": False, **kwargs}

        try:
            start_time = time.time()
            response = self.session.post(
                f"{self.base_url}/api/generate", json=payload, timeout=self.timeout
            )
            response_time = time.time() - start_time
            self._update_stats(response_time, response.status_code == 200)

            if response.status_code == 200:
                data = response.json()
                result = data.get("response", "")
                logger.debug(f"Prompt envoyé avec succès en {response_time:.3f}s")
                return result
            else:
                raise Exception(f"Erreur du modèle: HTTP {response.status_code}")
        except requests.Timeout:
            self._update_stats(self.timeout, False)
            raise Exception(f"Timeout après {self.timeout}s")
        except requests.RequestException as e:
            self._update_stats(0, False)
            raise Exception(f"Erreur de connexion: {e}")

    def classify_intent(
        self, message: str, available_intents: List[str], temperature: float = 0.1
    ) -> Tuple[str, float]:
        """Classifie une intention dans un message utilisateur"""
        intents_str = ", ".join(available_intents)

        prompt = f"""You are an intent classifier for a conversational AI system.

Analyze the following user message and classify it into one of the available intents.

Available intents: [{intents_str}]

User message: "{message}"

Instructions:
1. Choose the most appropriate intent from the available list
2. If no intent matches well, choose the closest one
3. Provide a confidence score between 0.0 and 1.0

Respond in this exact format:
Intent: <intent_name>
Confidence: <score>"""

        try:
            response = self.send_prompt(
                prompt, temperature=temperature, top_p=0.9, max_tokens=100
            )

            intent, confidence = self._parse_classification_response(
                response, available_intents
            )
            logger.debug(
                f"Classification: '{message}' -> {intent} (confiance: {confidence})"
            )
            return intent, confidence

        except Exception as e:
            logger.error(f"Erreur lors de la classification: {e}")
            fallback_intent = available_intents[0] if available_intents else "unknown"
            return fallback_intent, 0.0

    def _parse_classification_response(
        self, response: str, available_intents: List[str]
    ) -> Tuple[str, float]:
        """Parse la réponse de classification"""
        intent = None
        confidence = 0.0

        lines = response.strip().split("\n")

        for line in lines:
            line = line.strip()

            if line.startswith("Intent:"):
                intent_part = line[7:].strip()
                # Nettoyer l'intention extraite
                for avail_intent in available_intents:
                    if avail_intent.lower() in intent_part.lower():
                        intent = avail_intent
                        break
                if not intent:
                    intent = (
                        intent_part.split()[0]
                        if intent_part.split()
                        else available_intents[0]
                    )

            elif line.startswith("Confidence:"):
                conf_part = line[11:].strip()
                try:
                    confidence = float(conf_part)
                    confidence = max(0.0, min(1.0, confidence))
                except ValueError:
                    confidence = 0.5

        # Validation finale
        if not intent or intent not in available_intents:
            intent = available_intents[0] if available_intents else "unknown"
            confidence = max(0.1, confidence)

        return intent, confidence

    def _update_stats(self, response_time: float, success: bool) -> None:
        """Met à jour les statistiques"""
        self.stats["total_requests"] += 1

        if success:
            self.stats["successful_requests"] += 1
        else:
            self.stats["failed_requests"] += 1

        if response_time > 0:
            self.stats["total_response_time"] += response_time
            self.stats["avg_response_time"] = (
                self.stats["total_response_time"] / self.stats["total_requests"]
            )

    def get_stats(self) -> Dict:
        """Retourne les statistiques"""
        return self.stats.copy()


def test_ollama_client():
    """Test complet du client Ollama"""

    print("🧪 Test complet du client Ollama")
    print("================================")

    # Initialiser le client avec l'IP du bridge réseau
    client = OllamaClient(
        base_url="http://172.22.0.2:11434",
        model="llama3.2:1b",
        timeout=60,  # Timeout long pour la première requête
    )

    # Test 1: Health check
    print("\n1️⃣ Test de santé...")
    if client.health_check():
        print("   ✅ Service accessible")
    else:
        print("   ❌ Service non accessible")
        return False

    # Test 2: Classification d'intention simple
    print("\n2️⃣ Test de classification d'intention...")
    available_intents = ["greet", "goodbye", "question", "command"]
    test_messages = [
        "Hello, how are you?",
        "Goodbye, see you later!",
        "What time is it?",
        "Please show me the data",
    ]

    for message in test_messages:
        try:
            intent, confidence = client.classify_intent(message, available_intents)
            print(f"   📝 '{message}' -> {intent} (confiance: {confidence:.2f})")
        except Exception as e:
            print(f"   ❌ Erreur pour '{message}': {e}")

    # Test 3: Statistiques
    print("\n3️⃣ Statistiques d'utilisation...")
    stats = client.get_stats()
    print(f"   📊 Total requêtes: {stats['total_requests']}")
    print(f"   📊 Réussies: {stats['successful_requests']}")
    print(f"   📊 Échouées: {stats['failed_requests']}")
    print(f"   📊 Temps moyen: {stats['avg_response_time']:.2f}s")

    success_rate = (
        stats["successful_requests"] / stats["total_requests"] * 100
        if stats["total_requests"] > 0
        else 0
    )
    print(f"   📊 Taux de succès: {success_rate:.1f}%")

    # Validation finale
    if success_rate >= 80:
        print("\n🎉 Client Ollama validé avec succès !")
        return True
    else:
        print("\n❌ Taux de succès insuffisant")
        return False


if __name__ == "__main__":
    success = test_ollama_client()
    exit(0 if success else 1)
