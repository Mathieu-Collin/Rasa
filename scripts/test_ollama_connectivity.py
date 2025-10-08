#!/usr/bin/env python3
"""
Script de test pour trouver l'URL cor    # URLs à tester dans l'ordre de préférence
    urls_to_test = [
        "http://172.22.0.2:11434",     # IP du bridge réseau (PRIORITÉ)
        "http://localhost:11434",
        "http://127.0.0.1:11434",
        "http://host.docker.internal:11434",
        "http://192.168.65.254:11434",  # IP de host.docker.internal
        "http://172.17.0.1:11434",     # Gateway Docker par défaut
        "http://172.20.0.1:11434",     # Gateway trouvée plus tôt
        "http://10.0.2.2:11434",       # Gateway VirtualBox/VMware
    ] Ollama depuis le devcontainer
Teste plusieurs configurations possibles
"""

import sys
from pathlib import Path

import requests

# Ajouter le workspace au PYTHONPATH
workspace_path = Path(__file__).parent.parent
sys.path.insert(0, str(workspace_path))


def test_ollama_url(url: str, timeout: int = 10) -> bool:
    """Teste une URL Ollama"""
    try:
        print(f"🧪 Test: {url}")
        response = requests.get(f"{url}/api/version", timeout=timeout)
        if response.status_code == 200:
            version_data = response.json()
            print(f"   ✅ SUCCÈS! Version: {version_data.get('version', 'unknown')}")
            return True
        else:
            print(f"   ❌ Code erreur: {response.status_code}")
            return False
    except requests.exceptions.ConnectTimeout:
        print(f"   ⏱️  Timeout de connexion ({timeout}s)")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"   🔌 Erreur connexion: {str(e)[:100]}...")
        return False
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False


def test_ollama_tags(url: str, timeout: int = 10) -> bool:
    """Teste l'endpoint /api/tags pour voir les modèles disponibles"""
    try:
        print(f"📋 Test modèles: {url}/api/tags")
        response = requests.get(f"{url}/api/tags", timeout=timeout)
        if response.status_code == 200:
            tags_data = response.json()
            models = [
                model.get("name", "unknown") for model in tags_data.get("models", [])
            ]
            print(f"   ✅ Modèles disponibles: {models}")
            return True
        else:
            print(f"   ❌ Code erreur: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False


def main():
    """Teste différentes URLs pour Ollama"""
    print("🔍 RECHERCHE DE LA CONFIGURATION OLLAMA CORRECTE")
    print("=" * 60)

    # URLs à tester dans l'ordre de préférence
    urls_to_test = [
        "http://localhost:11434",
        "http://127.0.0.1:11434",
        "http://host.docker.internal:11434",
        "http://192.168.65.254:11434",  # IP de host.docker.internal
        "http://172.17.0.1:11434",  # Gateway Docker par défaut
        "http://172.20.0.1:11434",  # Gateway trouvée plus tôt
        "http://10.0.2.2:11434",  # Gateway VirtualBox/VMware
    ]

    working_urls = []

    for url in urls_to_test:
        print()
        if test_ollama_url(url, timeout=5):
            working_urls.append(url)
            # Tester aussi les modèles disponibles
            test_ollama_tags(url, timeout=10)

    print("\n" + "=" * 60)
    if working_urls:
        print("🎉 URLs FONCTIONNELLES TROUVÉES:")
        for url in working_urls:
            print(f"   ✅ {url}")

        print("\n📝 RECOMMANDATION:")
        print(f"   Utilisez: {working_urls[0]}")

        # Mise à jour automatique de la configuration
        try:
            print("\n🔧 MISE À JOUR DE LA CONFIGURATION...")
            update_config_file(working_urls[0])
            print("   ✅ Configuration mise à jour dans src/config/ollama_config.yml")
        except Exception as e:
            print(f"   ⚠️  Impossible de mettre à jour automatiquement: {e}")
    else:
        print("❌ AUCUNE URL FONCTIONNELLE TROUVÉE")
        print("\n💡 SOLUTIONS POSSIBLES:")
        print("   1. Vérifiez que le conteneur Ollama est démarré")
        print("   2. Vérifiez les ports exposés du conteneur")
        print("   3. Essayez de redémarrer le conteneur Ollama")
        print("   4. Vérifiez la configuration réseau Docker")


def update_config_file(working_url: str):
    """Met à jour le fichier de configuration avec l'URL qui fonctionne"""
    import yaml

    config_path = Path(__file__).parent.parent / "src/config/ollama_config.yml"

    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        config["ollama"]["base_url"] = working_url

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


if __name__ == "__main__":
    main()
