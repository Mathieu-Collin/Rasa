#!/usr/bin/env python3
"""
Script de diagnostic pour identifier les problèmes de rendu de graphiques frontend
"""

import json
import requests
from typing import Dict, Any

def test_rasa_response_format():
    """Teste le format de réponse Rasa pour les graphiques"""
    print("🔍 Test du Format de Réponse Rasa pour Graphiques")
    print("=" * 60)
    
    # Test avec une vraie requête
    test_message = "Show males aged 40 to 60 with NIHSS > 4"
    
    try:
        response = requests.post(
            "http://localhost:5005/webhooks/rest/webhook",
            json={"sender": "diagnostic_user", "message": test_message},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Réponse Rasa reçue (Status: {response.status_code})")
            
            # Analyser la structure de la réponse
            analyze_response_structure(data)
            
            # Générer des recommandations frontend
            generate_frontend_recommendations(data)
            
        else:
            print(f"❌ Erreur Rasa (Status: {response.status_code})")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"💥 Erreur de connexion: {str(e)}")

def analyze_response_structure(data: list):
    """Analyse la structure de la réponse Rasa"""
    print("\n📊 ANALYSE DE LA STRUCTURE DE RÉPONSE")
    print("-" * 40)
    
    if not data:
        print("❌ Réponse vide")
        return
    
    for i, message in enumerate(data):
        print(f"\n📋 Message {i+1}:")
        
        # Analyser les champs présents
        if isinstance(message, dict):
            print(f"  🔑 Champs disponibles: {list(message.keys())}")
            
            # Champ text/reply
            if 'text' in message:
                print(f"  📝 Texte: '{message['text']}'")
            elif 'reply' in message:
                print(f"  📝 Reply: '{message['reply']}'")
            
            # Champ custom (le plus important)
            if 'custom' in message:
                custom = message['custom']
                print(f"  🎨 Custom Type: {custom.get('type', 'N/A')}")
                
                if custom.get('type') == 'chart':
                    analyze_chart_data(custom.get('payload', {}))
                else:
                    print(f"  ⚠️  Type custom non-graphique: {custom.get('type')}")
            else:
                print("  ❌ PROBLÈME: Pas de champ 'custom' trouvé")
                print("     → Le frontend ne peut pas détecter les graphiques")
        else:
            print(f"  ❌ Message mal formaté: {type(message)}")

def analyze_chart_data(payload: Dict[str, Any]):
    """Analyse les données de graphique en détail"""
    print(f"\n  📈 DONNÉES DE GRAPHIQUE DÉTAILLÉES:")
    
    charts = payload.get('charts', [])
    print(f"    📊 Nombre de graphiques: {len(charts)}")
    
    for i, chart in enumerate(charts):
        print(f"\n    📋 Graphique {i+1}:")
        print(f"      🏷️  Titre: {chart.get('title', 'N/A')}")
        print(f"      📈 Type: {chart.get('chart_type', 'N/A')}")
        print(f"      📝 Description: {chart.get('description', 'N/A')}")
        
        metrics = chart.get('metrics', [])
        print(f"      📊 Nombre de métriques: {len(metrics)}")
        
        for j, metric in enumerate(metrics[:2]):  # Limiter à 2 pour la lisibilité
            print(f"        📋 Métrique {j+1}: {metric.get('title', 'N/A')}")
            print(f"           🎯 Valeur: {metric.get('metric', 'N/A')}")
            
            group_by = metric.get('group_by', [])
            if group_by:
                categories = []
                for group in group_by:
                    categories.extend(group.get('categories', []))
                print(f"           🏷️  Catégories: {', '.join(categories)}")

def generate_frontend_recommendations(data: list):
    """Génère des recommandations pour corriger le frontend"""
    print("\n\n🔧 RECOMMANDATIONS POUR LE FRONTEND")
    print("=" * 50)
    
    has_custom_field = any(
        isinstance(msg, dict) and 'custom' in msg 
        for msg in data
    )
    
    has_chart_type = any(
        isinstance(msg, dict) and 
        msg.get('custom', {}).get('type') == 'chart'
        for msg in data
    )
    
    if not has_custom_field:
        print("❌ PROBLÈME CRITIQUE: Pas de champ 'custom' dans les réponses")
        print("   → L'Action Server ne renvoie pas le bon format")
        print("   → Revenir à la documentation CHART_RESPONSE_FORMAT_ISSUE.md")
        return
    
    if not has_chart_type:
        print("❌ PROBLÈME: Le champ 'custom' existe mais type ≠ 'chart'")
        print("   → Vérifier la configuration de l'Action Server")
        return
    
    print("✅ FORMAT CORRECT: Les données sont bien structurées")
    print("\n📋 ACTIONS REQUISES CÔTÉ FRONTEND:")
    
    print("""
1. 🔍 DÉTECTION DES GRAPHIQUES
   Votre code frontend doit détecter: response.custom.type === "chart"
   
2. 📊 EXTRACTION DES DONNÉES
   Accéder aux données: response.custom.payload.charts
   
3. 🎨 RENDU DES GRAPHIQUES
   Pour chaque chart dans payload.charts:
   - chart.chart_type → Type de graphique (BAR, LINE, PIE, etc.)
   - chart.title → Titre du graphique
   - chart.metrics → Données à afficher
   
4. 📈 CONFIGURATION DES MÉTRIQUES
   Pour chaque métrique:
   - metric.title → Nom de la série
   - metric.metric → Valeur à mesurer (ex: DTN)
   - metric.group_by → Catégories de regroupement
   
5. 🔧 EXEMPLE DE CODE FRONTEND (JavaScript):
   
   function handleRasaResponse(messages) {
     messages.forEach(message => {
       if (message.custom && message.custom.type === 'chart') {
         const chartData = message.custom.payload;
         renderCharts(chartData.charts);
       } else {
         displayTextMessage(message.text || message.reply);
       }
     });
   }
   
   function renderCharts(charts) {
     charts.forEach(chart => {
       const element = createChartElement();
       const config = convertToChartConfig(chart);
       new Chart(element, config); // Exemple avec Chart.js
     });
   }
""")

def create_frontend_debug_snippet():
    """Génère un snippet de debug pour le frontend"""
    print("\n🧪 SNIPPET DE DEBUG POUR VOTRE FRONTEND:")
    print("-" * 45)
    
    debug_code = '''
// 🔍 SNIPPET DE DEBUG - Ajoutez ceci dans votre code frontend
function debugRasaResponse(response) {
    console.log('🔍 RASA RESPONSE DEBUG:', response);
    
    if (Array.isArray(response)) {
        response.forEach((message, index) => {
            console.log(`📋 Message ${index + 1}:`, message);
            
            if (message.custom) {
                console.log(`🎨 Custom Type: ${message.custom.type}`);
                
                if (message.custom.type === 'chart') {
                    console.log('📊 CHART DATA FOUND!');
                    console.log('📈 Charts:', message.custom.payload.charts);
                    
                    // Test de conversion des données
                    message.custom.payload.charts.forEach((chart, chartIndex) => {
                        console.log(`📋 Chart ${chartIndex + 1}:`);
                        console.log(`  📊 Type: ${chart.chart_type}`);
                        console.log(`  🏷️ Title: ${chart.title}`);
                        console.log(`  📈 Metrics Count: ${chart.metrics.length}`);
                    });
                } else {
                    console.log('⚠️ Custom type is not "chart"');
                }
            } else {
                console.log('❌ No custom field found');
            }
        });
    } else {
        console.log('⚠️ Response is not an array');
    }
}

// Utilisez cette fonction quand vous recevez une réponse de Rasa:
// debugRasaResponse(rasaResponse);
'''
    
    print(debug_code)

def main():
    """Fonction principale"""
    print("🚀 Diagnostic Frontend pour Graphiques Rasa")
    print("=" * 50)
    
    # Test du format de réponse
    test_rasa_response_format()
    
    # Générer le snippet de debug
    create_frontend_debug_snippet()
    
    print("\n\n🎯 PROCHAINES ÉTAPES:")
    print("1. Copiez le snippet de debug dans votre frontend")
    print("2. Testez avec la requête: 'Show males aged 40 to 60 with NIHSS > 4'")
    print("3. Vérifiez les logs de la console")
    print("4. Implémentez la logique de rendu des graphiques")

if __name__ == "__main__":
    main()