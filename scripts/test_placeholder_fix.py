#!/usr/bin/env python3
"""
Script de test spécifique pour valider la correction du problème des placeholders
"""

import json
import time

import requests


def test_placeholder_fix():
    """Teste que le problème des placeholders est résolu"""

    base_url = "http://localhost:5005"
    test_cases = [
        # Cas problématique original
        {
            "text": "Bonjour",
            "expected_intent": "greet",
            "should_not_contain": "[placeholder]",
            "description": "Salutation française (problème original)",
        },
        # Cas témoin - salutation anglaise
        {
            "text": "Hello",
            "expected_intent": "greet",
            "should_not_contain": "[placeholder]",
            "description": "Salutation anglaise (témoin)",
        },
        # Cas fallback intentionnel
        {
            "text": "give me a song",
            "expected_intent": "fallback",
            "should_not_contain": "[placeholder]",
            "description": "Demande hors scope (fallback volontaire)",
        },
    ]

    print("🔧 TEST DE CORRECTION DU PROBLÈME PLACEHOLDER")
    print("=" * 60)

    results = []

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['description']}")
        print(f"   📝 Texte: '{test_case['text']}'")
        print(f"   🎯 Intention attendue: {test_case['expected_intent']}")

        try:
            # Test du webhook complet
            webhook_response = requests.post(
                f"{base_url}/webhooks/rest/webhook",
                json={"sender": f"test-{i}", "message": test_case["text"]},
                timeout=30,
            )

            if webhook_response.status_code == 200:
                webhook_data = webhook_response.json()

                if webhook_data and len(webhook_data) > 0:
                    response_text = webhook_data[0].get("text", "")
                    print(f"   💬 Réponse: {response_text}")

                    # Vérifier qu'il n'y a pas de placeholder
                    has_placeholder = test_case["should_not_contain"] in response_text

                    if has_placeholder:
                        print("   ❌ ÉCHEC: Placeholder détecté dans la réponse!")
                        success = False
                    else:
                        print("   ✅ SUCCÈS: Pas de placeholder, réponse valide")
                        success = True

                    results.append(
                        {
                            "test": test_case["description"],
                            "text": test_case["text"],
                            "response": response_text,
                            "has_placeholder": has_placeholder,
                            "success": success,
                        }
                    )

                else:
                    print("   ❌ ERREUR: Aucune réponse reçue")
                    results.append(
                        {
                            "test": test_case["description"],
                            "text": test_case["text"],
                            "response": "",
                            "has_placeholder": False,
                            "success": False,
                        }
                    )
            else:
                print(f"   ❌ ERREUR API: {webhook_response.status_code}")
                results.append(
                    {
                        "test": test_case["description"],
                        "text": test_case["text"],
                        "response": "",
                        "has_placeholder": False,
                        "success": False,
                    }
                )

        except Exception as e:
            print(f"   ❌ EXCEPTION: {str(e)}")
            results.append(
                {
                    "test": test_case["description"],
                    "text": test_case["text"],
                    "response": "",
                    "has_placeholder": False,
                    "success": False,
                }
            )

        # Petite pause entre les tests
        time.sleep(2)

    # Résumé des résultats
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DU TEST DE CORRECTION")
    print("=" * 60)

    successes = sum(1 for r in results if r["success"])
    total = len(results)
    success_rate = (successes / total) * 100 if total > 0 else 0

    print(f"✅ Tests réussis: {successes}/{total} ({success_rate:.1f}%)")

    # Vérification spécifique du problème original
    bonjour_test = next((r for r in results if "Bonjour" in r["text"]), None)
    if bonjour_test:
        if bonjour_test["success"]:
            print("🎉 PROBLÈME RÉSOLU: 'Bonjour' ne retourne plus de placeholder!")
        else:
            print("🚨 PROBLÈME PERSISTANT: 'Bonjour' retourne encore un placeholder")
            print(f"   Réponse reçue: {bonjour_test['response']}")

    if successes < total:
        print("\n❌ ÉCHECS DÉTAILLÉS:")
        for result in results:
            if not result["success"]:
                placeholder_info = (
                    " (contient [placeholder])" if result["has_placeholder"] else ""
                )
                print(
                    f"   - {result['test']}: {result['response'][:100]}...{placeholder_info}"
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
            "   Démarrez le serveur avec: Ctrl+Shift+P > Tasks: Run Task > Rasa: Run (latest)"
        )
        exit(1)

    print("✅ Serveur RASA accessible")

    results = test_placeholder_fix()

    # Sauvegarde des résultats
    with open("/workspace/test_results_placeholder_fix.json", "w") as f:
        json.dump(
            {
                "timestamp": time.time(),
                "model_tested": "20251015-124110-glossy-ginger.tar.gz",
                "issue": "Placeholder fallback responses",
                "results": results,
                "summary": {
                    "total": len(results),
                    "successes": sum(1 for r in results if r["success"]),
                    "success_rate": (
                        sum(1 for r in results if r["success"]) / len(results)
                    )
                    * 100,
                    "bonjour_fixed": any(
                        r["success"] and "Bonjour" in r["text"] for r in results
                    ),
                },
            },
            f,
            indent=2,
        )

    print("\n💾 Résultats sauvegardés dans test_results_placeholder_fix.json")
