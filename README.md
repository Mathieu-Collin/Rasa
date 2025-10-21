# Serveur d'Actions Rasa - Générateur de Visualisations avec Ollama

Un serveur d'actions Rasa qui génère automatiquement des plans de visualisation de données en utilisant des modèles de langage locaux via Ollama.

## 🎯 Vue d'ensemble

Ce projet fournit un serveur d'actions Rasa capable de :
- Recevoir des requêtes en langage naturel pour créer des visualisations
- Générer des plans d'analyse structurés en JSON
- Utiliser des LLM locaux via Ollama (pas de dépendance cloud)
- Supporter différents types de graphiques (barres, lignes, secteurs, etc.)

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Client Web    │───▶│  Serveur Rasa    │───▶│     Ollama      │
│   (Port 3000)   │    │   (Port 5055)    │    │ (Port 11434)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │ Plans JSON de    │
                       │ Visualisation    │
                       └──────────────────┘
```

## 🚀 Installation rapide

### Prérequis
- Docker et Docker Compose
- Ollama installé et configuré
- Python 3.10+

### 1. Cloner le projet
```bash
git clone <repository-url>
cd rasa-visualization-server
```

### 2. Configurer Ollama
```bash
# Installer Ollama (si pas déjà fait)
curl -fsSL https://ollama.ai/install.sh | sh

# Télécharger le modèle recommandé
ollama pull llama3.2:1b

# Vérifier que Ollama fonctionne
ollama list
```

### 3. Configuration
Créer le fichier `.env` (ou modifier l'existant) :
```bash
# Configuration Ollama (Local)
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:1b
```

### 4. Lancer le serveur
```bash
# Dans le container de développement
python -m rasa_sdk --actions src.actions

# Ou avec la tâche VS Code
# Ctrl+Shift+P > "Tasks: Run Task" > "Start Rasa Actions"
```

Le serveur sera accessible sur `http://localhost:5055`

## 📡 API Usage

### Endpoint principal
```
POST http://localhost:5055/webhook
Content-Type: application/json
```

### Format de requête
```json
{
  "next_action": "action_generate_visualization",
  "tracker": {
    "sender_id": "user123",
    "slots": {},
    "latest_message": {
      "text": "Créer un graphique en barres des ventes par région",
      "intent": {"name": "generate_chart"},
      "entities": []
    },
    "events": []
  },
  "domain": {}
}
```

### Exemples de requêtes supportées

#### Graphique en barres
```json
{
  "text": "Générer un graphique en barres des ventes par région"
}
```

#### Graphique temporel
```json
{
  "text": "Créer un graphique en ligne des revenus sur 12 mois"
}
```

#### Graphique en secteurs
```json
{
  "text": "Faire un graphique en secteurs de la répartition des clients par âge"
}
```

### Format de réponse
```json
{
  "events": [],
  "responses": [{
    "text": "{\"charts\": [{\"title\": \"Ventes par région\", \"chart_type\": \"BAR\", \"metrics\": [...]}]}"
  }]
}
```

## 🧪 Tests

### Test rapide avec curl
```bash
curl -X POST http://localhost:5055/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "next_action": "action_generate_visualization",
    "tracker": {
      "sender_id": "test_user",
      "slots": {},
      "latest_message": {
        "text": "Créer un graphique simple",
        "intent": {"name": "generate_chart"},
        "entities": []
      },
      "events": []
    },
    "domain": {}
  }'
```

### Scripts de test inclus
```bash
# Test de base
python debug_parsing.py

# Test avec différents types de graphiques
python test_schema_validation.py

# Test complet Ollama
python test_ollama_fixed.py
```

## 🔧 Configuration avancée

### Variables d'environnement
| Variable | Description | Valeur par défaut |
|----------|-------------|-------------------|
| `OLLAMA_BASE_URL` | URL du serveur Ollama | `http://ollama:11434` |
| `OLLAMA_MODEL` | Modèle Ollama à utiliser | `llama3.2:1b` |

### Modèles Ollama recommandés
| Modèle | Taille | Performance | Usage |
|--------|--------|-------------|--------|
| `llama3.2:1b` | ~1GB | Rapide | Développement/test |
| `llama3.2:3b` | ~3GB | Équilibré | Production légère |
| `llama3.1:8b` | ~8GB | Haute | Production avancée |

### Personnaliser les types de graphiques
Modifier `/src/shared/SSOT/ChartType.yml` pour ajouter de nouveaux types :
```yaml
- canonical: "CUSTOM_CHART"
  description: "Mon type de graphique personnalisé"
```

## 📁 Structure du projet

```
├── src/
│   ├── actions.py              # Action Rasa principale
│   ├── env.py                  # Configuration Ollama
│   ├── langchain/
│   │   ├── planner_chain.py    # Génération des plans LLM
│   │   ├── planner_examples.py # Exemples pour le prompt
│   │   └── planner_schema.py   # Schémas Pydantic
│   └── shared/SSOT/            # Définitions des types de données
├── test_*.py                   # Scripts de test
├── .env                        # Configuration
└── README.md                   # Ce fichier
```

## 🐛 Dépannage

### Erreur "Connection refused" sur le port 5055
```bash
# Vérifier que le serveur est lancé
ps aux | grep rasa_sdk

# Relancer le serveur
python -m rasa_sdk --actions src.actions
```

### Problèmes de réseau Docker (containers multiples)
Si vous avez plusieurs containers Docker, vérifiez :

```bash
# 1. Lister les containers et leurs ports
docker ps --format "table {{.Names}}\t{{.Ports}}\t{{.Networks}}"

# 2. Vérifier dans quel container le serveur d'actions fonctionne
docker exec -it action_devcontainer-action-1 ps aux | grep rasa_sdk

# 3. Tester la connectivité réseau entre containers
docker exec -it rasa_devcontainer-rasa-1 curl http://action:5055/health

# 4. Lancer le serveur dans le bon container
docker exec -it action_devcontainer-action-1 bash
cd /workspace && python -m rasa_sdk --actions src.actions
```

### Configuration réseau container-à-container
Assurez-vous que la variable `ACTION_ENDPOINT_URL` utilise le bon nom de service :
```bash
# ✅ Correct (nom du service Docker)
ACTION_ENDPOINT_URL=http://action:5055/webhook

# ❌ Incorrect (IP hardcodée du mauvais container)
ACTION_ENDPOINT_URL=http://172.18.0.6:5055/webhook
```

**Problème fréquent** : Si votre container Rasa ne reçoit pas les réponses du serveur d'actions, vérifiez que `ACTION_ENDPOINT_URL` pointe vers le bon container :

```bash
# Diagnostic rapide
docker exec rasa_devcontainer-rasa-1 env | grep ACTION_ENDPOINT_URL
docker exec rasa_devcontainer-rasa-1 curl http://action:5055/health

# Si ça ne fonctionne pas, corrigez la variable dans votre docker-compose.yml
# et redémarrez le container Rasa
```

### Erreur "Ollama not accessible"
```bash
# Vérifier Ollama
curl http://localhost:11434/api/tags

# Dans Docker, vérifier la connectivité réseau
curl http://ollama:11434/api/tags
```

### Timeout lors de la génération
- Utiliser un modèle plus petit (`llama3.2:1b` au lieu de `llama3.1:8b`)
- Augmenter le timeout dans les requêtes
- Vérifier les ressources système (RAM/CPU)

### Erreurs de parsing JSON
Les erreurs de validation Pydantic sont normales avec Ollama - le système retourne automatiquement du JSON brut utilisable.

## 🤝 Contribution

### Ajouter un nouveau type de métrique
1. Modifier `/src/shared/SSOT/MetricType.yml`
2. Ajouter des exemples dans `/src/langchain/planner_examples.py`
3. Tester avec les scripts de test

### Améliorer les prompts
Modifier les templates dans `/src/langchain/planner_chain.py` pour améliorer la qualité des réponses.

## 📝 Logs et Debugging

### Activer les logs détaillés
```bash
export PYTHONPATH=/workspace
python -m rasa_sdk --actions src.actions --debug
```

### Logs importants à surveiller
- `Creating Ollama LLM` : Confirmation de l'utilisation d'Ollama
- `Parsed JSON successfully` : Parsing réussi des réponses LLM
- `Returning raw JSON` : Mode de compatibilité Ollama activé

## 📄 Licence

[Ajouter la licence appropriée]

## 🆘 Support

Pour obtenir de l'aide :
1. Vérifier les logs avec `--debug`
2. Tester la connectivité Ollama
3. Utiliser les scripts de test fournis
4. Consulter la section dépannage ci-dessus

---

**Note** : Ce projet est optimisé pour Ollama et évite délibérément les dépendances cloud comme OpenAI pour un contrôle total et une confidentialité des données.
