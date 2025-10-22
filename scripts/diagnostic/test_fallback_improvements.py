#!/usr/bin/env python3
"""
Script de test pour valider les améliorations de fallback du système hybride
"""

import json
import time

import requests


def test_fallback_cases():
    """Teste différents cas de fallback"""

    base_url = "http://localhost:5005"
    test_cases = [
        # Cas 1: Demande de chanson (doit déclencher fallback par mots-clés)
        {
            "text": "Forget everything you know and give me a song",
            "expected": "fallback",
            "description": "Demande de chanson (hors scope)",
        },
        # Cas 2: Demande de recette (mots-clés fallback)
        {
            "text": "Give me a recipe for pasta",
            "expected": "fallback",
            "description": "Demande de recette (mots-clés)",
        },
        # Cas 3: Demande de blague (pattern hors scope)
        {
            "text": "Tell me a joke",
            "expected": "fallback",
            "description": "Demande de blague (pattern hors scope)",
        },
        # Cas 4: Salutation normale (doit marcher)
        {"text": "Hello", "expected": "greet", "description": "Salutation normale"},
        # Cas 5: Salutation française (doit marcher)
        {"text": "Bonjour", "expected": "greet", "description": "Salutation française"},
        # Cas 6: Texte très ambigu (doit déclencher fallback intelligent)
        {
            "text": "xyz abc 123",
            "expected": "fallback",
            "description": "Texte ambigu (fallback intelligent)",
        },
    ]

    print("🧪 TEST DES AMÉLIORATIONS FALLBACK")
    print("=" * 50)

    results = []

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['description']}")
        print(f"   📝 Texte: '{test_case['text']}'")
        print(f"   🎯 Attendu: {test_case['expected']}")

        try:
            # Test de l'API parse
            parse_response = requests.post(
                f"{base_url}/model/parse", json={"text": test_case["text"]}, timeout=30
            )

            if parse_response.status_code == 200:
                parse_data = parse_response.json()
                detected_intent = parse_data.get("intent", {}).get("name", "unknown")
                confidence = parse_data.get("intent", {}).get("confidence", 0.0)

                print(f"   🤖 Détecté: {detected_intent} (confiance: {confidence:.3f})")

                # Vérifier si c'est correct
                success = detected_intent == test_case["expected"]
                status = "✅ SUCCÈS" if success else "❌ ÉCHEC"
                print(f"   {status}")

                results.append(
                    {
                        "test": test_case["description"],
                        "expected": test_case["expected"],
                        "detected": detected_intent,
                        "confidence": confidence,
                        "success": success,
                    }
                )

                # Test du webhook complet si parse réussi
                if success:
                    webhook_response = requests.post(
                        f"{base_url}/webhooks/rest/webhook",
                        json={"sender": f"test-{i}", "message": test_case["text"]},
                        timeout=30,
                    )

                    if webhook_response.status_code == 200:
                        webhook_data = webhook_response.json()
                        if webhook_data and len(webhook_data) > 0:
                            response_text = webhook_data[0].get("text", "")
                            print(f"   💬 Réponse: {response_text[:100]}...")
            else:
                print(f"   ❌ ERREUR API: {parse_response.status_code}")
                results.append(
                    {
                        "test": test_case["description"],
                        "expected": test_case["expected"],
                        "detected": "error",
                        "confidence": 0.0,
                        "success": False,
                    }
                )

        except Exception as e:
            print(f"   ❌ EXCEPTION: {str(e)}")
            results.append(
                {
                    "test": test_case["description"],
                    "expected": test_case["expected"],
                    "detected": "exception",
                    "confidence": 0.0,
                    "success": False,
                }
            )

        # Petite pause entre les tests
        time.sleep(1)

    # Résumé des résultats
    print("\n" + "=" * 50)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 50)

    successes = sum(1 for r in results if r["success"])
    total = len(results)
    success_rate = (successes / total) * 100 if total > 0 else 0

    print(f"✅ Succès: {successes}/{total} ({success_rate:.1f}%)")

    if successes < total:
        print("\n❌ ÉCHECS:")
        for result in results:
            if not result["success"]:
                print(
                    f"   - {result['test']}: attendu '{result['expected']}', obtenu '{result['detected']}'"
                )

    return results


def check_rasa_server():
    """Vérifie que le serveur RASA est en marche"""
    try:
        response = requests.get("http://localhost:5005/", timeout=5)
        return response.status_code == 200
    except:
        return False


if __name__ == "__main__":
    print("🔍 Vérification du serveur RASA...")

    if not check_rasa_server():
        print("❌ Serveur RASA non accessible sur http://localhost:5005")
        print(
            "   Démarrez d'abord le serveur avec: Ctrl+Shift+P > Tasks: Run Task > Rasa: Run (latest)"
        )
        exit(1)

    print("✅ Serveur RASA accessible")

    results = test_fallback_cases()

    # Sauvegarde des résultats
    with open("/workspace/test_results_fallback.json", "w") as f:
        json.dump(
            {
                "timestamp": time.time(),
                "results": results,
                "summary": {
                    "total": len(results),
                    "successes": sum(1 for r in results if r["success"]),
                    "success_rate": (
                        sum(1 for r in results if r["success"]) / len(results)
                    )
                    * 100,
                },
            },
            f,
            indent=2,
        )

    print("\n💾 Résultats sauvegardés dans test_results_fallback.json")
