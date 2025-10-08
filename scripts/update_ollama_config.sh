#!/bin/bash
# Script pour mettre à jour automatiquement l'IP Ollama dans tous les fichiers
# À utiliser si l'IP du bridge réseau change

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 MISE À JOUR DE LA CONFIGURATION OLLAMA${NC}"
echo "=============================================="

# Fonction pour obtenir l'IP d'Ollama depuis le réseau Docker
get_ollama_ip() {
    # Essayer de trouver l'IP d'Ollama dans le réseau bridge
    OLLAMA_IP=$(docker inspect Ollama 2>/dev/null | jq -r '.[0].NetworkSettings.Networks."ollama-rasa-bridge".IPAddress' 2>/dev/null || echo "")
    
    if [ -z "$OLLAMA_IP" ] || [ "$OLLAMA_IP" = "null" ]; then
        echo -e "${YELLOW}⚠️  Impossible de détecter automatiquement l'IP d'Ollama${NC}"
        echo -e "${YELLOW}   Veuillez entrer l'IP manuellement:${NC}"
        read -p "IP Ollama: " OLLAMA_IP
    fi
    
    echo "$OLLAMA_IP"
}

# Fonction pour mettre à jour un fichier
update_file() {
    local file="$1"
    local old_ip="$2"
    local new_ip="$3"
    
    if [ -f "$file" ]; then
        if grep -q "$old_ip" "$file"; then
            sed -i "s|$old_ip|$new_ip|g" "$file"
            echo -e "   ${GREEN}✅ $file${NC}"
        else
            echo -e "   ${YELLOW}⏭️  $file (aucun changement)${NC}"
        fi
    else
        echo -e "   ${RED}❌ $file (fichier introuvable)${NC}"
    fi
}

# Obtenir la nouvelle IP
NEW_IP=$(get_ollama_ip)
if [ -z "$NEW_IP" ]; then
    echo -e "${RED}❌ IP Ollama non spécifiée, arrêt du script${NC}"
    exit 1
fi

echo -e "${BLUE}📍 Nouvelle IP Ollama: $NEW_IP${NC}"
echo ""

# Anciennes IPs à remplacer
OLD_IPS=(
    "http://localhost:11434"
    "http://127.0.0.1:11434"
    "http://host.docker.internal:11434"
    "http://172.22.0.2:11434"
    "http://172.17.0.2:11434"
)

NEW_URL="http://$NEW_IP:11434"

echo -e "${BLUE}🔄 Mise à jour des fichiers de configuration...${NC}"

# Liste des fichiers à mettre à jour
FILES=(
    "$WORKSPACE_ROOT/src/config/ollama_config.yml"
    "$WORKSPACE_ROOT/src/config/hybrid_pipeline_config.yml"
    "$WORKSPACE_ROOT/src/core/config_hybrid_test.yml"
    "$WORKSPACE_ROOT/src/components/llm_intent_router.py"
    "$WORKSPACE_ROOT/tests/components/test_llm_intent_router.py"
    "$WORKSPACE_ROOT/scripts/test_ollama_client.py"
    "$WORKSPACE_ROOT/scripts/test_ollama_basic.py"
    "$WORKSPACE_ROOT/scripts/test_llm_intent_router_logic.py"
    "$WORKSPACE_ROOT/scripts/test_error_handling_system.py"
    "$WORKSPACE_ROOT/scripts/test_debug_logging.py"
)

# Mettre à jour chaque fichier
for file in "${FILES[@]}"; do
    for old_ip in "${OLD_IPS[@]}"; do
        update_file "$file" "$old_ip" "$NEW_URL"
    done
done

echo ""
echo -e "${BLUE}🧪 Test de connectivité...${NC}"

# Tester la nouvelle configuration
if curl -s --connect-timeout 5 "$NEW_URL/api/version" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Ollama accessible sur $NEW_URL${NC}"
else
    echo -e "${RED}❌ Ollama non accessible sur $NEW_URL${NC}"
    echo -e "${YELLOW}   Vérifiez que le conteneur Ollama est démarré et sur le bon réseau${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Mise à jour terminée !${NC}"
echo -e "${BLUE}📝 Fichiers mis à jour: ${#FILES[@]}${NC}"
echo -e "${BLUE}🔗 Nouvelle URL: $NEW_URL${NC}"