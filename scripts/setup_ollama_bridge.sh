#!/bin/bash
# Script pour connecter les conteneurs Ollama et RASA
# À exécuter sur la machine hôte (WSL)

echo "🌉 Configuration du bridge réseau Docker pour Ollama et RASA"
echo "=========================================================="

# Étape 1: Identifier les réseaux et conteneurs
echo "📋 Identification des conteneurs..."
OLLAMA_CONTAINER=$(docker ps --filter "name=ollama" --format "{{.Names}}" | head -1)
RASA_CONTAINER=$(docker ps --filter "name=rasa" --format "{{.Names}}" | head -1)

echo "   Conteneur Ollama: $OLLAMA_CONTAINER"
echo "   Conteneur RASA: $RASA_CONTAINER"

if [ -z "$OLLAMA_CONTAINER" ]; then
    echo "❌ Conteneur Ollama non trouvé"
    exit 1
fi

if [ -z "$RASA_CONTAINER" ]; then
    echo "❌ Conteneur RASA non trouvé"
    exit 1
fi

# Étape 2: Créer un réseau bridge si nécessaire
NETWORK_NAME="ollama-rasa-bridge"
echo "🌐 Création du réseau bridge '$NETWORK_NAME'..."

if docker network ls | grep -q "$NETWORK_NAME"; then
    echo "   ✅ Réseau '$NETWORK_NAME' existe déjà"
else
    docker network create --driver bridge "$NETWORK_NAME"
    echo "   ✅ Réseau '$NETWORK_NAME' créé"
fi

# Étape 3: Connecter les conteneurs au réseau
echo "🔌 Connexion des conteneurs au réseau..."

# Connecter Ollama
if docker network inspect "$NETWORK_NAME" | grep -q "$OLLAMA_CONTAINER"; then
    echo "   ✅ $OLLAMA_CONTAINER déjà connecté"
else
    docker network connect "$NETWORK_NAME" "$OLLAMA_CONTAINER"
    echo "   ✅ $OLLAMA_CONTAINER connecté au réseau"
fi

# Connecter RASA
if docker network inspect "$NETWORK_NAME" | grep -q "$RASA_CONTAINER"; then
    echo "   ✅ $RASA_CONTAINER déjà connecté"
else
    docker network connect "$NETWORK_NAME" "$RASA_CONTAINER"
    echo "   ✅ $RASA_CONTAINER connecté au réseau"
fi

# Étape 4: Obtenir les IPs des conteneurs
echo "📊 Configuration réseau finale:"
OLLAMA_IP=$(docker inspect "$OLLAMA_CONTAINER" | jq -r ".[0].NetworkSettings.Networks.\"$NETWORK_NAME\".IPAddress")
RASA_IP=$(docker inspect "$RASA_CONTAINER" | jq -r ".[0].NetworkSettings.Networks.\"$NETWORK_NAME\".IPAddress")

echo "   🤖 Ollama IP: $OLLAMA_IP"
echo "   🤖 RASA IP: $RASA_IP"

# Étape 5: Configuration suggérée
echo ""
echo "🎯 CONFIGURATION SUGGÉRÉE:"
echo "   URL Ollama pour RASA: http://$OLLAMA_IP:11434"
echo "   Ou utiliser le nom: http://$OLLAMA_CONTAINER:11434"
echo ""
echo "✅ Configuration terminée ! Les conteneurs peuvent maintenant communiquer."

# Test de connectivité
echo "🧪 Test de connectivité..."
if docker exec "$RASA_CONTAINER" sh -c "curl -s --connect-timeout 5 http://$OLLAMA_IP:11434/api/version" > /dev/null 2>&1; then
    echo "   ✅ Connectivité OK: RASA → Ollama"
else
    echo "   ⚠️  Connectivité à vérifier: RASA → Ollama"
fi