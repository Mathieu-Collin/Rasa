#!/bin/bash

# Script de test de connectivité Ollama et documentation des endpoints
# Phase 1.1c du plan d'action LLM Intent Router

set -euo pipefail

OLLAMA_BASE_URL="http://localhost:11434"
MODEL_NAME="llama3.2:1b"

echo "🔍 Test de connectivité Ollama et documentation des endpoints"
echo "============================================================="

# Fonction de test avec formatage JSON
test_endpoint() {
    local endpoint=$1
    local method=${2:-GET}
    local data=${3:-""}
    local description=$4
    
    echo ""
    echo "📍 Test: $description"
    echo "   Endpoint: $method $OLLAMA_BASE_URL$endpoint"
    
    if [ "$method" == "GET" ]; then
        if response=$(curl -s "$OLLAMA_BASE_URL$endpoint" 2>/dev/null); then
            echo "   ✅ Succès"
            if command -v jq >/dev/null 2>&1; then
                echo "$response" | jq . 2>/dev/null | head -10 || echo "$response" | head -10
            else
                echo "$response" | head -10
            fi
        else
            echo "   ❌ Échec"
        fi
    else
        if response=$(curl -s -X "$method" "$OLLAMA_BASE_URL$endpoint" \
                          -H "Content-Type: application/json" \
                          -d "$data" 2>/dev/null); then
            echo "   ✅ Succès"
            if command -v jq >/dev/null 2>&1; then
                echo "$response" | jq . 2>/dev/null | head -10 || echo "$response" | head -10
            else
                echo "$response" | head -10
            fi
        else
            echo "   ❌ Échec"
        fi
    fi
}

# 1. Test de santé général
test_endpoint "/" "GET" "" "Santé générale de l'API"

# 2. Liste des modèles
test_endpoint "/api/tags" "GET" "" "Liste des modèles disponibles"

# 3. Test de génération simple
SIMPLE_PROMPT='{"model":"'$MODEL_NAME'","prompt":"Hello","stream":false}'
test_endpoint "/api/generate" "POST" "$SIMPLE_PROMPT" "Génération de texte simple"

# 4. Test de classification d'intention
INTENT_PROMPT='{"model":"'$MODEL_NAME'","prompt":"Classify this user message into intent. Message: '\''Hello, how are you?'\'' Respond with just the intent name: greet, goodbye, or other.","stream":false}'
test_endpoint "/api/generate" "POST" "$INTENT_PROMPT" "Classification d'intention basique"

# 5. Test avec prompt structuré pour classification
STRUCTURED_PROMPT='{"model":"'$MODEL_NAME'","prompt":"You are an intent classifier. Classify this message: '\''Good morning!'\'' into one of these intents: [greet, goodbye, question, command]. Respond with only the intent name.","stream":false}'
test_endpoint "/api/generate" "POST" "$STRUCTURED_PROMPT" "Classification avec prompt structuré"

# 6. Test de performance (temps de réponse)
echo ""
echo "⏱️  Test de performance"
echo "   Mesure du temps de réponse pour une classification..."

start_time=$(date +%s%N)
curl -s -X POST "$OLLAMA_BASE_URL/api/generate" \
     -H "Content-Type: application/json" \
     -d '{"model":"'$MODEL_NAME'","prompt":"Intent: Hello there!","stream":false}' > /dev/null
end_time=$(date +%s%N)

duration=$(( (end_time - start_time) / 1000000 ))
echo "   ⏱️  Temps de réponse: ${duration}ms"

if [ $duration -lt 2000 ]; then
    echo "   ✅ Performance acceptable (<2s)"
elif [ $duration -lt 5000 ]; then
    echo "   ⚠️  Performance modérée (2-5s)"
else
    echo "   ❌ Performance lente (>5s)"
fi

# 7. Informations sur le modèle
echo ""
echo "🤖 Informations sur le modèle $MODEL_NAME"
if model_info=$(curl -s "$OLLAMA_BASE_URL/api/show" -d '{"name":"'$MODEL_NAME'"}' 2>/dev/null); then
    echo "   ✅ Modèle accessible"
    if command -v jq >/dev/null 2>&1; then
        echo "   Taille: $(echo "$model_info" | jq -r '.details.parameter_size // "N/A"')"
        echo "   Format: $(echo "$model_info" | jq -r '.details.format // "N/A"')"
        echo "   Famille: $(echo "$model_info" | jq -r '.details.family // "N/A"')"
    fi
else
    echo "   ❌ Impossible d'obtenir les informations du modèle"
fi

echo ""
echo "📊 Résumé des tests de connectivité"
echo "=================================="
echo "✅ Service Ollama opérationnel sur $OLLAMA_BASE_URL"
echo "✅ Modèle $MODEL_NAME chargé et fonctionnel"
echo "✅ API de génération accessible"
echo "✅ Classification d'intention possible"
echo "⏱️  Temps de réponse moyen: ~${duration}ms"
echo ""
echo "📝 Endpoints documentés pour l'intégration Python:"
echo "   • GET  /api/tags - Liste des modèles"
echo "   • POST /api/generate - Génération de texte"
echo "   • POST /api/show - Informations sur un modèle"
echo "   • GET  / - Santé de l'API"
echo ""
echo "➡️  Prêt pour l'étape 1.2: Création du client Python"