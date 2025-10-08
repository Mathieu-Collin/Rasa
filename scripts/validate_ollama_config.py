#!/usr/bin/env python3
"""
Script de validation de la configuration Ollama
Phase 1.3 du plan d'action LLM Intent Router
"""

from pathlib import Path

import yaml


def validate_ollama_config():
    """Valide la configuration Ollama et teste les fonctionnalités"""

    print("🔧 Validation de la configuration Ollama")
    print("=========================================")

    # Charger la configuration
    config_path = Path("/workspace/src/config/ollama_config.yml")

    if not config_path.exists():
        print("❌ Fichier de configuration non trouvé")
        return False

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        print("✅ Configuration chargée avec succès")
    except yaml.YAMLError as e:
        print(f"❌ Erreur de parsing YAML: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur lors du chargement: {e}")
        return False

    # Validation de la structure
    print("\n📋 Validation de la structure...")

    required_sections = ["ollama", "hybrid_decision", "intents", "monitoring"]
    for section in required_sections:
        if section in config:
            print(f"   ✅ Section '{section}' présente")
        else:
            print(f"   ❌ Section '{section}' manquante")
            return False

    # Validation des paramètres Ollama
    print("\n🤖 Validation des paramètres Ollama...")
    ollama_config = config.get("ollama", {})

    required_params = ["base_url", "model", "timeout"]
    for param in required_params:
        if param in ollama_config:
            value = ollama_config[param]
            print(f"   ✅ {param}: {value}")
        else:
            print(f"   ❌ Paramètre '{param}' manquant")
            return False

    # Validation des prompts
    print("\n📝 Validation des prompts...")
    intent_config = ollama_config.get("intent_classification", {})

    if "prompt_template" in intent_config:
        prompt = intent_config["prompt_template"]
        if "{available_intents}" in prompt and "{user_message}" in prompt:
            print("   ✅ Template de prompt valide")
        else:
            print("   ❌ Template de prompt invalide (placeholders manquants)")
            return False
    else:
        print("   ❌ Template de prompt manquant")
        return False

    # Validation des intentions
    print("\n🎯 Validation des intentions...")
    intents_config = config.get("intents", {})

    if "supported_intents" in intents_config:
        intents = intents_config["supported_intents"]
        print(f"   ✅ {len(intents)} intentions configurées: {', '.join(intents)}")

        # Vérifier les descriptions
        descriptions = intents_config.get("intent_descriptions", {})
        for intent in intents:
            if intent in descriptions:
                print(
                    f"   ✅ Description pour '{intent}': {descriptions[intent][:50]}..."
                )
            else:
                print(f"   ⚠️  Description manquante pour '{intent}'")
    else:
        print("   ❌ Liste des intentions manquante")
        return False

    # Validation des seuils de décision
    print("\n⚖️  Validation des seuils de décision...")
    hybrid_config = config.get("hybrid_decision", {})

    thresholds = [
        "nlu_priority_threshold",
        "llm_priority_threshold",
        "agreement_threshold",
    ]
    for threshold in thresholds:
        if threshold in hybrid_config:
            value = hybrid_config[threshold]
            if 0.0 <= value <= 1.0:
                print(f"   ✅ {threshold}: {value}")
            else:
                print(f"   ❌ {threshold} hors limites [0.0, 1.0]: {value}")
                return False
        else:
            print(f"   ❌ Seuil '{threshold}' manquant")
            return False

    # Test du template de prompt
    print("\n🧪 Test du template de prompt...")
    try:
        test_intents = intents_config["supported_intents"][:3]  # Prendre 3 intentions
        test_message = "Hello, how are you?"

        prompt = intent_config["prompt_template"].format(
            available_intents=", ".join(test_intents), user_message=test_message
        )

        if len(prompt) > 50:  # Vérifier que le prompt n'est pas vide
            print(f"   ✅ Template généré correctement ({len(prompt)} caractères)")
        else:
            print("   ❌ Template généré trop court")
            return False

    except Exception as e:
        print(f"   ❌ Erreur lors du test du template: {e}")
        return False

    # Résumé de la validation
    print("\n📊 Résumé de la configuration:")
    print(f"   • URL Ollama: {ollama_config['base_url']}")
    print(f"   • Modèle: {ollama_config['model']}")
    print(f"   • Timeout: {ollama_config['timeout']}s")
    print(f"   • Intentions: {len(intents_config['supported_intents'])}")
    print(f"   • Seuil NLU: {hybrid_config['nlu_priority_threshold']}")
    print(f"   • Seuil LLM: {hybrid_config['llm_priority_threshold']}")
    print(
        f"   • Fallback: {'Activé' if hybrid_config.get('fallback_to_nlu', False) else 'Désactivé'}"
    )

    print("\n🎉 Configuration validée avec succès !")
    return True


def test_config_loading():
    """Test le chargement de la configuration depuis Python"""
    print("\n🐍 Test du chargement Python...")

    try:
        # Simuler le chargement depuis le client
        config_path = "/workspace/src/config/ollama_config.yml"
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Extraire les paramètres pour le client
        ollama_params = config["ollama"]
        client_config = {
            "base_url": ollama_params["base_url"],
            "model": ollama_params["model"],
            "timeout": ollama_params["timeout"],
        }

        print(f"   ✅ Configuration chargée pour client: {client_config}")

        # Test du prompt
        intent_config = ollama_params["intent_classification"]
        prompt_template = intent_config["prompt_template"]

        test_prompt = prompt_template.format(
            available_intents="greet, goodbye, question", user_message="Hello there!"
        )

        print(f"   ✅ Prompt généré: {len(test_prompt)} caractères")
        return True

    except Exception as e:
        print(f"   ❌ Erreur lors du test Python: {e}")
        return False


if __name__ == "__main__":
    success1 = validate_ollama_config()
    success2 = test_config_loading()

    if success1 and success2:
        print("\n🚀 Configuration prête pour l'intégration !")
        exit(0)
    else:
        print("\n💥 Problèmes détectés dans la configuration")
        exit(1)
