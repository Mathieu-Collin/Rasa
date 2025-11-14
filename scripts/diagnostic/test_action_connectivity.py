#!/usr/bin/env python3
"""
Script de test pour diagnostiquer la connectivité avec l'Action Server
"""

import time

import requests


def test_endpoint(url: str, name: str) -> bool:
    """Teste un endpoint spécifique"""
    print(f"\n🔍 Test de {name}: {url}")

    test_payload = {
        "next_action": "action_generate_visualization",
        "tracker": {
            "sender_id": "test_user",
            "slots": {},
            "latest_message": {
                "text": "Créer un graphique simple",
                "intent": {"name": "generate_visualization"},
                "entities": [],
            },
            "events": [],
        },
        "domain": {},
    }

    try:
        response = requests.post(
            url,
            json=test_payload,
            timeout=10,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 200:
            print(f"✅ {name} : SUCCÈS (Status: {response.status_code})")
            print(f"   Response: {response.text[:200]}...")
            return True
        else:
            print(f"⚠️ {name} : Status {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
            return False

    except requests.exceptions.ConnectionError:
        print(f"❌ {name} : Connection refused")
        return False
    except requests.exceptions.Timeout:
        print(f"⏱️ {name} : Timeout")
        return False
    except Exception as e:
        print(f"💥 {name} : Erreur - {str(e)}")
        return False


def main():
    print("🚀 Test de connectivité Action Server Rasa")
    print("=" * 50)

    # Liste des endpoints à tester
    endpoints = [
        ("http://172.18.0.6:6055/webhook", "IP fixe actuelle"),
        ("http://host.docker.internal:6055/webhook", "host.docker.internal"),
        ("http://localhost:6055/webhook", "localhost"),
        ("http://action_devcontainer-action-1:6055/webhook", "nom de container"),
        ("http://action:6055/webhook", "nom simplifié"),
    ]

    results = {}

    for url, name in endpoints:
        results[name] = test_endpoint(url, name)
        time.sleep(1)  # Pause entre les tests

    print("\n📊 RÉSUMÉ DES TESTS")
    print("=" * 50)

    working_endpoints = []
    for name, success in results.items():
        status = "✅ FONCTIONNE" if success else "❌ ÉCHEC"
        print(f"{name:25} : {status}")
        if success:
            working_endpoints.append(name)

    if working_endpoints:
        print(f"\n🎉 Endpoints fonctionnels : {', '.join(working_endpoints)}")
        print("\n💡 Recommandation : Utiliser un des endpoints qui fonctionne")
        print("   pour mettre à jour ACTION_ENDPOINT_URL")
    else:
        print("\n🚨 AUCUN endpoint ne fonctionne !")
        print("   ➡️ L'Action Server n'est probablement pas démarré")
        print("   ➡️ Vérifier dans le container action_devcontainer-action-1")


if __name__ == "__main__":
    main()
