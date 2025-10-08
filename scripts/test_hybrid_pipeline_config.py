#!/usr/bin/env python3
"""
Test de validation de la configuration pipeline hybride
Valide la syntaxe YAML et la coherence de la configuration
"""

from pathlib import Path

import yaml


def test_hybrid_pipeline_config():
    """Test de validation de la configuration pipeline hybride"""

    print("🔧 Test de validation - Configuration Pipeline Hybride")
    print("====================================================")

    # 1. Test de chargement YAML
    print("\n1️⃣ Test de chargement YAML...")
    config_path = Path("/workspace/src/config/hybrid_pipeline_config.yml")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        print("   ✅ Fichier YAML chargé avec succès")
    except Exception as e:
        print(f"   ❌ Erreur chargement YAML: {e}")
        return False

    # 2. Validation de la structure
    print("\n2️⃣ Validation de la structure de configuration...")

    required_fields = [
        "version",
        "recipe",
        "language",
        "pipeline",
        "policies",
        "importers",
    ]
    missing_fields = []

    for field in required_fields:
        if field not in config:
            missing_fields.append(field)

    if missing_fields:
        print(f"   ❌ Champs manquants: {missing_fields}")
        return False
    else:
        print("   ✅ Tous les champs requis présents")

    # 3. Validation du pipeline
    print("\n3️⃣ Validation du pipeline...")

    pipeline = config.get("pipeline", [])
    if not pipeline:
        print("   ❌ Pipeline vide")
        return False

    print(f"   📊 Pipeline contient {len(pipeline)} composants:")

    # Recherche de notre composant LLM Intent Router
    llm_router_found = False
    tokenizer_found = False
    diet_found = False

    for i, component in enumerate(pipeline, 1):
        if isinstance(component, dict):
            component_name = component.get("name", "Unknown")
        else:
            component_name = component

        print(f"      {i}. {component_name}")

        # Vérifications spécifiques
        if "WhitespaceTokenizer" in component_name:
            tokenizer_found = True
        elif "DIETClassifier" in component_name:
            diet_found = True
        elif "llm_intent_router.LLMIntentRouter" in component_name:
            llm_router_found = True

            # Validation de la configuration du LLM Router
            if isinstance(component, dict):
                print("      🔍 Configuration LLM Intent Router:")

                # Vérification des paramètres Ollama
                ollama_enabled = component.get("ollama_enabled", False)
                ollama_url = component.get("ollama_base_url", "")
                ollama_model = component.get("ollama_model", "")

                print(f"         Ollama activé: {ollama_enabled}")
                print(f"         URL Ollama: {ollama_url}")
                print(f"         Modèle: {ollama_model}")

                # Vérification des seuils
                nlu_threshold = component.get("nlu_priority_threshold", 0)
                llm_threshold = component.get("llm_priority_threshold", 0)
                agreement_threshold = component.get("agreement_threshold", 0)

                print(f"         Seuil NLU: {nlu_threshold}")
                print(f"         Seuil LLM: {llm_threshold}")
                print(f"         Seuil accord: {agreement_threshold}")

                # Validation des seuils
                if not (0.0 <= nlu_threshold <= 1.0):
                    print("         ❌ Seuil NLU invalide")
                elif not (0.0 <= llm_threshold <= 1.0):
                    print("         ❌ Seuil LLM invalide")
                elif not (0.0 <= agreement_threshold <= 1.0):
                    print("         ❌ Seuil accord invalide")
                elif llm_threshold < nlu_threshold:
                    print("         ⚠️  Seuil LLM < Seuil NLU (recommandé inverse)")
                else:
                    print("         ✅ Seuils valides")

    # Vérifications de cohérence
    validation_results = []

    if not tokenizer_found:
        validation_results.append("❌ Tokenizer manquant (requis en première position)")
    else:
        validation_results.append("✅ Tokenizer présent")

    if not diet_found:
        validation_results.append(
            "❌ DIETClassifier manquant (requis pour NLU de base)"
        )
    else:
        validation_results.append("✅ DIETClassifier présent")

    if not llm_router_found:
        validation_results.append("❌ LLM Intent Router manquant")
    else:
        validation_results.append("✅ LLM Intent Router présent")

    # 4. Validation des politiques
    print("\n4️⃣ Validation des politiques...")

    policies = config.get("policies", [])
    if not policies:
        print("   ❌ Aucune politique définie")
        return False

    print(f"   📊 {len(policies)} politiques définies:")
    for i, policy in enumerate(policies, 1):
        if isinstance(policy, dict):
            policy_name = policy.get("name", "Unknown")
        else:
            policy_name = policy
        print(f"      {i}. {policy_name}")

    validation_results.append("✅ Politiques définies")

    # 5. Validation des importeurs
    print("\n5️⃣ Validation des importeurs...")

    importers = config.get("importers", [])
    overlay_importer_found = False

    for importer in importers:
        if isinstance(importer, dict):
            importer_name = importer.get("name", "")
            if "OverlayImporter" in importer_name:
                overlay_importer_found = True

    if overlay_importer_found:
        validation_results.append("✅ OverlayImporter présent")
    else:
        validation_results.append(
            "⚠️  OverlayImporter manquant (fonctionnalité multi-locale)"
        )

    # 6. Test de compatibilité avec la configuration existante
    print("\n6️⃣ Test de compatibilité avec configuration existante...")

    try:
        existing_config_path = Path("/workspace/src/core/config.yml")
        with open(existing_config_path, "r", encoding="utf-8") as f:
            existing_config = yaml.safe_load(f)

        # Comparaison des versions
        existing_version = existing_config.get("version", "unknown")
        new_version = config.get("version", "unknown")

        if existing_version == new_version:
            validation_results.append("✅ Version compatible")
        else:
            validation_results.append(
                f"⚠️  Version différente: existante={existing_version}, nouvelle={new_version}"
            )

        # Comparaison du recipe
        existing_recipe = existing_config.get("recipe", "unknown")
        new_recipe = config.get("recipe", "unknown")

        if existing_recipe == new_recipe:
            validation_results.append("✅ Recipe compatible")
        else:
            validation_results.append(
                f"⚠️  Recipe différent: existant={existing_recipe}, nouveau={new_recipe}"
            )

    except Exception as e:
        validation_results.append(
            f"⚠️  Impossible de comparer avec config existante: {e}"
        )

    # 7. Résumé des résultats
    print("\n7️⃣ Résumé de validation...")

    for result in validation_results:
        print(f"   {result}")

    # Score final
    success_count = sum(1 for result in validation_results if result.startswith("✅"))
    total_count = len(validation_results)
    score = (success_count / total_count * 100) if total_count > 0 else 0

    print(f"\n📊 Score de validation: {score:.1f}% ({success_count}/{total_count})")

    if score >= 85:
        print("🎉 CONFIGURATION PIPELINE VALIDÉE - Prête pour l'utilisation !")
        return True
    elif score >= 70:
        print(
            "⚠️  Configuration partiellement validée - Quelques ajustements recommandés"
        )
        return True
    else:
        print("❌ Configuration nécessite des corrections majeures")
        return False


if __name__ == "__main__":
    success = test_hybrid_pipeline_config()
    exit(0 if success else 1)
