#!/usr/bin/env python3
"""
Test d'intégration complète: Configuration + Client Ollama
Phase 1 - Validation finale de l'infrastructure LLM
"""

import sys
from pathlib import Path

import yaml

# Ajouter le chemin du client
sys.path.insert(0, "/workspace/scripts")
from test_ollama_client import OllamaClient


def load_config():
    """Charge la configuration Ollama"""
    config_path = Path("/workspace/src/config/ollama_config.yml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_integration():
    """Test d'intégration complète configuration + client"""

    print("🚀 Test d'intégration Configuration + Client Ollama")
    print("====================================================")

    # 1. Charger la configuration
    print("\n1️⃣ Chargement de la configuration...")
    try:
        config = load_config()
        ollama_config = config["ollama"]
        intents_config = config["intents"]
        hybrid_config = config["hybrid_decision"]
        print("   ✅ Configuration chargée")
    except Exception as e:
        print(f"   ❌ Erreur de chargement: {e}")
        return False

    # 2. Initialiser le client avec la config
    print("\n2️⃣ Initialisation du client avec configuration...")
    try:
        client_params = {
            "base_url": ollama_config["base_url"],
            "model": ollama_config["model"],
            "timeout": ollama_config["timeout"],
        }
        client = OllamaClient(**client_params)
        print(f"   ✅ Client initialisé: {client}")
    except Exception as e:
        print(f"   ❌ Erreur d'initialisation: {e}")
        return False

    # 3. Test de santé
    print("\n3️⃣ Test de santé du service...")
    if client.health_check():
        print("   ✅ Service Ollama accessible")
    else:
        print("   ❌ Service Ollama inaccessible")
        return False

    # 4. Test du prompt configuré
    print("\n4️⃣ Test du prompt configuré...")
    try:
        intent_classification = ollama_config["intent_classification"]
        prompt_template = intent_classification["prompt_template"]
        available_intents = intents_config["supported_intents"]

        test_message = "Hello, how are you today?"
        formatted_prompt = prompt_template.format(
            available_intents=", ".join(available_intents), user_message=test_message
        )

        print(f"   ✅ Prompt formaté ({len(formatted_prompt)} caractères)")

        # Test du prompt avec le client
        classification_params = intent_classification.get("classification_params", {})
        response = client.send_prompt(formatted_prompt, **classification_params)
        print(f"   ✅ Réponse LLM reçue: {response[:100]}...")

    except Exception as e:
        print(f"   ❌ Erreur de test du prompt: {e}")
        return False

    # 5. Test de classification avec les intentions configurées
    print("\n5️⃣ Test de classification avec intentions configurées...")
    try:
        available_intents = intents_config["supported_intents"]
        test_messages = [
            ("Hello, how are you?", "greet"),
            ("Goodbye, see you later!", "goodbye"),
            ("What time is it?", "question"),
            ("Show me the dashboard", "command"),
            ("blah blah unclear message", "fallback"),
        ]

        correct_predictions = 0
        total_predictions = len(test_messages)

        for message, expected_intent in test_messages:
            try:
                predicted_intent, confidence = client.classify_intent(
                    message, available_intents, temperature=0.1
                )

                is_correct = predicted_intent == expected_intent
                correct_predictions += is_correct

                status = "✅" if is_correct else "⚠️"
                print(
                    f"   {status} '{message}' -> {predicted_intent} (attendu: {expected_intent}, conf: {confidence:.2f})"
                )

            except Exception as e:
                print(f"   ❌ Erreur pour '{message}': {e}")

        accuracy = correct_predictions / total_predictions * 100
        print(
            f"   📊 Précision: {accuracy:.1f}% ({correct_predictions}/{total_predictions})"
        )

        if accuracy >= 60:  # Seuil acceptable pour un modèle 1B
            print("   ✅ Précision acceptable")
        else:
            print("   ⚠️  Précision faible")

    except Exception as e:
        print(f"   ❌ Erreur de test de classification: {e}")
        return False

    # 6. Test des seuils de décision
    print("\n6️⃣ Validation des seuils de décision...")
    try:
        nlu_threshold = hybrid_config["nlu_priority_threshold"]
        llm_threshold = hybrid_config["llm_priority_threshold"]
        agreement_threshold = hybrid_config["agreement_threshold"]

        print(f"   ✅ Seuil priorité NLU: {nlu_threshold}")
        print(f"   ✅ Seuil priorité LLM: {llm_threshold}")
        print(f"   ✅ Seuil d'accord: {agreement_threshold}")

        # Test de la logique de décision
        if nlu_threshold < llm_threshold:
            print("   ✅ Logique de seuils cohérente")
        else:
            print("   ⚠️  Seuils incohérents (NLU devrait être < LLM)")

    except Exception as e:
        print(f"   ❌ Erreur de validation des seuils: {e}")
        return False

    # 7. Statistiques finales
    print("\n7️⃣ Statistiques du client...")
    stats = client.get_stats()
    print(f"   📊 Total requêtes: {stats['total_requests']}")
    print(f"   📊 Requêtes réussies: {stats['successful_requests']}")
    print(f"   📊 Temps moyen: {stats['avg_response_time']:.2f}s")

    success_rate = (
        (stats["successful_requests"] / stats["total_requests"] * 100)
        if stats["total_requests"] > 0
        else 0
    )
    print(f"   📊 Taux de succès: {success_rate:.1f}%")

    # Critères de validation finale
    criteria_met = [
        success_rate >= 90,  # Au moins 90% de succès
        stats["avg_response_time"] < 3.0,  # Temps moyen < 3s
        accuracy >= 50,  # Précision >= 50% (tolérant pour modèle 1B)
    ]

    print("\n📋 Critères de validation:")
    print(
        f"   {'✅' if criteria_met[0] else '❌'} Taux de succès >= 90%: {success_rate:.1f}%"
    )
    print(
        f"   {'✅' if criteria_met[1] else '❌'} Temps moyen < 3s: {stats['avg_response_time']:.2f}s"
    )
    print(f"   {'✅' if criteria_met[2] else '❌'} Précision >= 50%: {accuracy:.1f}%")

    all_criteria_met = all(criteria_met)

    if all_criteria_met:
        print("\n🎉 PHASE 1 VALIDÉE - Infrastructure LLM Ollama opérationnelle !")
        print("🚀 Prêt pour la Phase 2: Développement du LLM Intent Router")
        return True
    else:
        print("\n⚠️  Certains critères non atteints - Optimisation requise")
        return False


if __name__ == "__main__":
    success = test_integration()
    exit(0 if success else 1)
