#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de test pour valider le système de debug logging du LLM Intent Router
Teste différents scénarios et affiche les logs    try:
        router = LLMIntentRouter.create(
            config=config['llm_intent_router'],
            model_storage=None,
            resource=None,
            execution_context=None
        )lés pour chaque décision
"""

import logging
import os
import sys
import tempfile
from pathlib import Path

import yaml

# Ajouter le workspace au PYTHONPATH
workspace_path = Path(__file__).parent.parent
sys.path.insert(0, str(workspace_path))

from src.components.llm_intent_router import LLMIntentRouter


def setup_debug_logging():
    """Configure le logging pour afficher les messages de debug"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def create_test_config():
    """Crée une configuration de test avec debug activé"""
    config = {
        "llm_intent_router": {
            "debug_logging": True,  # DEBUG ACTIVÉ
            "ollama_enabled": True,
            "ollama_base_url": "http://172.22.0.2:11434",  # IP du bridge réseau
            "ollama_model": "llama3.2:1b",
            "ollama_config_path": "src/config/ollama_config.yml",
            "nlu_priority_threshold": 0.8,
            "llm_priority_threshold": 0.9,
            "agreement_threshold": 0.1,
            "fallback_to_nlu": True,
            "cache_enabled": True,
            "cache_ttl": 300,
            "timeout": 30,
            "max_retries": 3,
        }
    }

    # Créer un fichier de config temporaire
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(config, f, default_flow_style=False)
        return f.name


def create_mock_message(text: str, nlu_intent: str, nlu_confidence: float):
    """Crée un message de test avec intention NLU simulée"""

    class MockMessage:
        def __init__(self, text: str, intent: str, confidence: float):
            self._data = {
                "text": text,
                "intent": {"name": intent, "confidence": confidence},
            }

        def get(self, key: str, default=None):
            return self._data.get(key, default)

        def set(self, key: str, value):
            self._data[key] = value

    return MockMessage(text, nlu_intent, nlu_confidence)


def test_debug_scenarios():
    """Teste différents scénarios avec debug logging activé"""

    print("🚀 DÉMARRAGE DES TESTS DEBUG LOGGING")
    print("=" * 80)

    setup_debug_logging()

    # Créer la config de test
    config_file = create_test_config()

    try:
        # Initialiser le routeur avec debug activé
        config_data = yaml.safe_load(open(config_file))["llm_intent_router"]
        router = LLMIntentRouter.create(
            config=config_data,  # Passer directement la config du component
            model_storage=None,
            resource=None,
            execution_context=None,
        )

        print(f"✅ Routeur initialisé avec debug_logging = {router._debug_logging}")
        print("\n")

        # Scénario 1: NLU très confiant (>= 0.8)
        print("🧪 SCÉNARIO 1: NLU HAUTE CONFIANCE")
        print("-" * 50)
        message1 = create_mock_message("Bonjour", "greet", 0.95)
        router.process([message1])
        print("\n")

        # Scénario 2: NLU moins confiant (< 0.8)
        print("🧪 SCÉNARIO 2: NLU CONFIANCE MOYENNE")
        print("-" * 50)
        message2 = create_mock_message(
            "Je veux faire un graphique", "visualization", 0.65
        )
        router.process([message2])
        print("\n")

        # Scénario 3: Message ambigu
        print("🧪 SCÉNARIO 3: MESSAGE AMBIGU")
        print("-" * 50)
        message3 = create_mock_message("Aide moi", "help", 0.50)
        router.process([message3])
        print("\n")

        # Scénario 4: Commande plus complexe
        print("🧪 SCÉNARIO 4: COMMANDE COMPLEXE")
        print("-" * 50)
        message4 = create_mock_message(
            "Peux-tu créer un graphique en barres des ventes par région",
            "visualization",
            0.70,
        )
        router.process([message4])
        print("\n")

        # Afficher les statistiques finales
        print("📊 STATISTIQUES FINALES")
        print("-" * 50)
        stats = router.get_stats()
        for key, value in stats.items():
            print(f"   {key}: {value}")

        print("\n✅ TESTS DEBUG TERMINÉS AVEC SUCCÈS")

    except Exception as e:
        print(f"❌ ERREUR DURANT LES TESTS: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Nettoyer le fichier temporaire
        try:
            os.unlink(config_file)
        except Exception:
            pass


def test_ollama_unavailable():
    """Teste le comportement quand Ollama n'est pas disponible"""
    print("\n🧪 TEST SUPPLÉMENTAIRE: OLLAMA INDISPONIBLE")
    print("-" * 50)

    # Créer config avec Ollama désactivé
    config = {
        "llm_intent_router": {
            "debug_logging": True,
            "ollama_enabled": False,  # OLLAMA DÉSACTIVÉ pour ce test
            "ollama_base_url": "http://172.22.0.2:11434",  # IP du bridge réseau
            "nlu_priority_threshold": 0.8,
            "fallback_to_nlu": True,
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(config, f, default_flow_style=False)
        config_file = f.name

    try:
        router = LLMIntentRouter.create(
            config={"llm_intent_router": config["llm_intent_router"]},
            model_storage=None,
            resource=None,
            execution_context=None,
        )

        message = create_mock_message("Test sans Ollama", "test", 0.60)
        router.process([message])

    finally:
        os.unlink(config_file)


if __name__ == "__main__":
    test_debug_scenarios()
    test_ollama_unavailable()
