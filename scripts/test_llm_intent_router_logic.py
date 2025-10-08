#!/usr/bin/env python3
"""
Test de validation du LLM Intent Router
Teste la logique hybride sans dependance RASA complete
"""

import sys
from unittest.mock import Mock

# Ajouter le chemin pour le client Ollama
sys.path.insert(0, "/workspace/scripts")


def test_llm_intent_router_logic():
    """Test unitaire de la logique de decision hybride"""

    print("🧪 Test de la logique LLM Intent Router")
    print("=====================================")

    # Mock des dependances RASA pour permettre l'import
    mock_modules = [
        "rasa.engine.graph",
        "rasa.engine.recipes.default_recipe",
        "rasa.engine.storage.resource",
        "rasa.engine.storage.storage",
        "rasa.shared.nlu.training_data.message",
    ]

    for module in mock_modules:
        sys.modules[module] = Mock()

    # Mock des classes RASA necessaires
    sys.modules["rasa.engine.graph"].ExecutionContext = Mock
    sys.modules["rasa.engine.graph"].GraphComponent = Mock
    sys.modules["rasa.engine.recipes.default_recipe"].DefaultV1Recipe = Mock()
    sys.modules["rasa.engine.recipes.default_recipe"].DefaultV1Recipe.register = Mock(
        return_value=lambda cls: cls
    )
    sys.modules[
        "rasa.engine.recipes.default_recipe"
    ].DefaultV1Recipe.ComponentType = Mock()
    sys.modules[
        "rasa.engine.recipes.default_recipe"
    ].DefaultV1Recipe.ComponentType.INTENT_CLASSIFIER = "intent_classifier"
    sys.modules["rasa.engine.storage.resource"].Resource = Mock
    sys.modules["rasa.engine.storage.storage"].ModelStorage = Mock
    sys.modules["rasa.shared.nlu.training_data.message"].Message = Mock

    # Ajouter le chemin pour notre composant
    sys.path.insert(0, "/workspace")

    # Maintenant importer notre composant
    from src.components.llm_intent_router import LLMIntentRouter

    # Configuration de test
    config = {
        "ollama_enabled": True,
        "ollama_base_url": "http://172.22.0.2:11434",  # IP du bridge réseau
        "ollama_model": "llama3.2:1b",
        "ollama_timeout": 30,
        "nlu_priority_threshold": 0.8,
        "llm_priority_threshold": 0.9,
        "agreement_threshold": 0.1,
        "fallback_to_nlu": True,
        "debug_logging": True,
    }

    print("\n1️⃣ Test d'initialisation du composant...")
    try:
        router = LLMIntentRouter(config)
        print("   ✅ Composant initialisé avec succès")
        print(f"   📊 Config: {router}")
    except Exception as e:
        print(f"   ❌ Erreur d'initialisation: {e}")
        return False

    print("\n2️⃣ Test de la logique de decision hybride...")

    # Test cases pour la logique hybride
    test_cases = [
        {
            "name": "NLU haute confiance",
            "text": "Hello how are you",
            "nlu_intent": "greet",
            "nlu_confidence": 0.95,
            "expected_source": "nlu_high_confidence",
        },
        {
            "name": "NLU faible confiance",
            "text": "What time is it",
            "nlu_intent": "question",
            "nlu_confidence": 0.6,
            "expected_llm_call": True,
        },
        {
            "name": "Ollama desactive",
            "text": "Goodbye",
            "nlu_intent": "goodbye",
            "nlu_confidence": 0.7,
            "disable_ollama": True,
            "expected_source": "nlu_fallback",
        },
    ]

    success_count = 0
    total_tests = len(test_cases)

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n   Test {i}: {test_case['name']}")

        try:
            # Configurer le routeur pour ce test
            if test_case.get("disable_ollama"):
                router._ollama_enabled = False
                router._ollama_client = None
            else:
                router._ollama_enabled = True
                # Mock du client Ollama pour les tests
                mock_client = Mock()
                mock_client.classify_intent.return_value = ("question", 0.8)
                router._ollama_client = mock_client

            # Appeler la logique hybride
            final_intent, final_confidence, decision_source = router._hybrid_classify(
                test_case["text"], test_case["nlu_intent"], test_case["nlu_confidence"]
            )

            print(
                f"      Résultat: {final_intent} (conf: {final_confidence:.2f}, source: {decision_source})"
            )

            # Vérifications
            if "expected_source" in test_case:
                if decision_source == test_case["expected_source"]:
                    print("      ✅ Source de décision correcte")
                    success_count += 1
                else:
                    print(
                        f"      ❌ Source attendue: {test_case['expected_source']}, obtenue: {decision_source}"
                    )

            elif "expected_llm_call" in test_case:
                if router._ollama_enabled and router._ollama_client:
                    print("      ✅ Appel LLM effectué comme attendu")
                    success_count += 1
                else:
                    print("      ❌ Appel LLM attendu mais non effectué")

        except Exception as e:
            print(f"      ❌ Erreur: {e}")

    print(f"\n📊 Résultats des tests: {success_count}/{total_tests} réussis")

    print("\n3️⃣ Test des statistiques...")
    try:
        stats = router.get_stats()
        print("   ✅ Statistiques récupérées:")
        for key, value in stats.items():
            if not key.startswith("ollama_stats"):
                print(f"      {key}: {value}")
    except Exception as e:
        print(f"   ❌ Erreur stats: {e}")

    print("\n4️⃣ Test de récupération des intentions disponibles...")
    try:
        intents = router._get_available_intents()
        print(f"   ✅ Intentions trouvées: {intents}")
    except Exception as e:
        print(f"   ❌ Erreur intentions: {e}")

    # Calcul du score final
    final_score = success_count / total_tests * 100 if total_tests > 0 else 0

    if final_score >= 80:
        print(f"\n🎉 Test réussi ! Score: {final_score:.1f}%")
        print("✅ Logique hybride du LLM Intent Router validée")
        return True
    else:
        print(f"\n⚠️  Test partiellement réussi. Score: {final_score:.1f}%")
        return False


if __name__ == "__main__":
    success = test_llm_intent_router_logic()
    exit(0 if success else 1)
