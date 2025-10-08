#!/usr/bin/env python3
"""
Script de test simple pour valider le client Ollama
Phase 1.2 du plan d'action LLM Intent Router
"""

import time

import requests


def test_ollama_basic():
    """Test basique du service Ollama"""

    print("🧪 Test basique du service Ollama")
    print("================================")

    # Configuration Ollama - IP du bridge réseau
    base_url = "http://172.22.0.2:11434"
    model = "llama3.2:1b"

    # Test 1: Health check
    print("\n1️⃣ Test de santé du service...")
    try:
        response = requests.get(f"{base_url}/", timeout=10)
        if response.status_code == 200:
            print("   ✅ Service Ollama accessible")
        else:
            print(f"   ❌ Service non accessible: HTTP {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"   ❌ Erreur de connexion: {e}")
        return False

    # Test 2: Classification simple
    print("\n2️⃣ Test de classification d'intention...")

    prompt = """You are an intent classifier.
    
Classify this message: "Hello, how are you?"

Available intents: [greet, goodbye, question]

Respond with:
Intent: <intent_name>
Confidence: <0.0-1.0>"""

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.1,
        "max_tokens": 50,
    }

    try:
        start_time = time.time()
        response = requests.post(f"{base_url}/api/generate", json=payload, timeout=30)
        response_time = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            result = data.get("response", "")
            print(f"   ✅ Classification réussie en {response_time:.2f}s")
            print(f"   📝 Réponse: {result.strip()}")

            # Parser la réponse
            intent = None
            confidence = None
            for line in result.split("\n"):
                line = line.strip()
                if line.startswith("Intent:"):
                    intent = line[7:].strip()
                elif line.startswith("Confidence:"):
                    try:
                        confidence = float(line[11:].strip())
                    except ValueError:
                        pass

            print(f"   🎯 Intention extraite: {intent}")
            print(f"   📊 Confiance: {confidence}")

        else:
            print(f"   ❌ Erreur de classification: HTTP {response.status_code}")
            return False

    except requests.RequestException as e:
        print(f"   ❌ Erreur lors de la classification: {e}")
        return False

    # Test 3: Performance
    print("\n3️⃣ Test de performance (5 requêtes)...")

    simple_payload = {
        "model": model,
        "prompt": "Hello",
        "stream": False,
        "max_tokens": 10,
    }

    times = []
    for i in range(5):
        try:
            start_time = time.time()
            response = requests.post(
                f"{base_url}/api/generate", json=simple_payload, timeout=30
            )
            response_time = time.time() - start_time

            if response.status_code == 200:
                times.append(response_time)
                print(f"   Requête {i + 1}: {response_time:.2f}s")
            else:
                print(f"   Requête {i + 1}: Échec HTTP {response.status_code}")

        except requests.RequestException as e:
            print(f"   Requête {i + 1}: Erreur {e}")

    if times:
        avg_time = sum(times) / len(times)
        print(f"   📊 Temps de réponse moyen: {avg_time:.2f}s")
        print(f"   📊 Min: {min(times):.2f}s, Max: {max(times):.2f}s")

        if avg_time < 2.0:
            print("   ✅ Performance acceptable")
        elif avg_time < 5.0:
            print("   ⚠️  Performance modérée")
        else:
            print("   ❌ Performance lente")

    print("\n🎉 Tests terminés avec succès !")
    return True


if __name__ == "__main__":
    success = test_ollama_basic()
    exit(0 if success else 1)
