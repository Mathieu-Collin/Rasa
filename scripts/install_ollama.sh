#!/bin/bash

# Script d'installation et configuration Ollama pour le projet LLM Intent Router
# Compatible avec les environnements Linux/Ubuntu (incluant dev containers)

set -euo pipefail

OLLAMA_VERSION="latest"
OLLAMA_MODEL="llama3.1:8b"
OLLAMA_PORT="11434"

echo "🚀 Installation et Configuration Ollama pour LLM Intent Router"
echo "============================================================="

# Fonction de logging
log_info() {
    echo "ℹ️  $1"
}

log_success() {
    echo "✅ $1"
}

log_error() {
    echo "❌ $1"
}

log_warning() {
    echo "⚠️  $1"
}

# Path to project root (scripts/ is inside the repo root)
PROJ_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OLLAMA_SAVE_DIR="$PROJ_ROOT/ollama_save"

# Ensure the host folder used by docker-compose (./ollama_save) exists
ensure_ollama_save() {
    if [ ! -d "$OLLAMA_SAVE_DIR" ]; then
        log_info "Création du dossier de persistance Ollama: $OLLAMA_SAVE_DIR"
        mkdir -p "$OLLAMA_SAVE_DIR"
        # Try to set owner to the current user so Docker can write; ignore failures
        chown "$(id -u):$(id -g)" "$OLLAMA_SAVE_DIR" 2>/dev/null || true
        chmod 750 "$OLLAMA_SAVE_DIR" 2>/dev/null || true
    else
        log_info "Dossier de persistance Ollama existant: $OLLAMA_SAVE_DIR"
    fi
}

# Vérifier si Ollama est déjà installé
if command -v ollama >/dev/null 2>&1; then
    log_info "Ollama déjà installé: $(ollama --version)"
else
    log_info "Installation d'Ollama..."
    
    # Télécharger et installer Ollama
    if curl -fsSL https://ollama.ai/install.sh | sh; then
        log_success "Ollama installé avec succès"
    else
        log_error "Échec de l'installation d'Ollama"
        exit 1
    fi
fi

# Vérifier que Ollama est dans le PATH
if ! command -v ollama >/dev/null 2>&1; then
    log_error "Ollama n'est pas dans le PATH après installation"
    log_info "Vous devrez peut-être redémarrer votre terminal ou exécuter: source ~/.bashrc"
    exit 1
fi

log_info "Démarrage du service Ollama..."

# Démarrer Ollama en arrière-plan
# Ensure ollama_save exists (useful when docker-compose bind-mounts ./ollama_save)
ensure_ollama_save

ollama serve > /tmp/ollama.log 2>&1 &
OLLAMA_PID=$!

# Attendre que le service démarre
log_info "Attente du démarrage du service (max 60s)..."
for i in {1..60}; do
    if curl -s http://localhost:$OLLAMA_PORT/api/tags >/dev/null 2>&1; then
        log_success "Service Ollama démarré sur le port $OLLAMA_PORT"
        break
    fi
    
    if [ $i -eq 60 ]; then
        log_error "Timeout: le service Ollama n'a pas démarré dans les 60 secondes"
        if ps -p $OLLAMA_PID > /dev/null; then
            kill $OLLAMA_PID
        fi
        exit 1
    fi
    
    sleep 1
done

# Télécharger le modèle LLM
log_info "Téléchargement du modèle $OLLAMA_MODEL (cela peut prendre plusieurs minutes)..."
if ollama pull $OLLAMA_MODEL; then
    log_success "Modèle $OLLAMA_MODEL téléchargé avec succès"
else
    log_error "Échec du téléchargement du modèle $OLLAMA_MODEL"
    exit 1
fi

# Vérifier que le modèle est bien disponible
log_info "Vérification du modèle..."
if ollama list | grep -q "llama3.1"; then
    log_success "Modèle llama3.1 disponible"
else
    log_warning "Le modèle llama3.1 ne semble pas être disponible"
fi

# Test de base du modèle
log_info "Test de base du modèle..."
TEST_RESPONSE=$(ollama run $OLLAMA_MODEL "Hello, respond with just 'OK'" --format json 2>/dev/null || echo "")
if [[ "$TEST_RESPONSE" == *"OK"* ]]; then
    log_success "Test de base du modèle réussi"
else
    log_warning "Le test de base du modèle n'a pas donné la réponse attendue"
fi

# Afficher les informations finales
echo ""
log_success "🎉 Installation et configuration Ollama terminées !"
echo ""
echo "📋 Informations importantes:"
echo "   • Service Ollama: http://localhost:$OLLAMA_PORT"
echo "   • Modèle installé: $OLLAMA_MODEL"
echo "   • PID du processus: $OLLAMA_PID"
echo "   • Logs: /tmp/ollama.log"
echo ""
echo "🔧 Commandes utiles:"
echo "   • Lister les modèles: ollama list"
echo "   • Tester le modèle: ollama run $OLLAMA_MODEL 'Hello'"
echo "   • Arrêter Ollama: kill $OLLAMA_PID"
echo "   • Redémarrer: ollama serve"
echo ""
echo "➡️  Vous pouvez maintenant continuer avec la Phase 1.2 du plan d'action"