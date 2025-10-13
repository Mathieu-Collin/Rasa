"""
Client Ollama pour LLM Intent Router
Client autonome pour la communication avec l'API Ollama
"""

import json
import logging
import requests
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client pour l'API Ollama"""
    
    def __init__(self, base_url: str = "http://ollama-gpu:11434", 
                 model: str = "llama3.2:1b", timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        
        logger.info(f"OllamaClient initialisé: {self.base_url}, modèle: {self.model}")
        
    def health_check(self) -> bool:
        """Vérifie si Ollama est accessible"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False
    
    def classify_intent(self, user_message: str, available_intents: List[str], 
                       prompt_template: str) -> Tuple[Optional[str], Optional[float]]:
        """Classifie une intention avec Ollama"""
        try:
            # Construire le prompt
            prompt = prompt_template.format(
                available_intents=', '.join(available_intents),
                user_message=user_message
            )
            
            # Préparer la requête
            data = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "max_tokens": 50
                }
            }
            
            # Envoyer la requête
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=data,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.error(f"Ollama API error: {response.status_code}")
                return None, None
                
            result = response.json()
            llm_response = result.get('response', '')
            
            # Parser la réponse avec validation
            intent, confidence = self._parse_llm_response(llm_response, available_intents)
            
            if intent and confidence is not None:
                logger.debug(f"Classification réussie: {intent} ({confidence})")
                return intent, confidence
            else:
                logger.warning(f"Impossible de parser la réponse: {llm_response}")
                return None, None
                
        except Exception as e:
            logger.error(f"Erreur classification Ollama: {e}")
            return None, None
    
    def _parse_llm_response(self, llm_response: str, available_intents: List[str] = None) -> Tuple[Optional[str], Optional[float]]:
        """Parse la réponse du LLM pour extraire intention et confiance"""
        try:
            lines = llm_response.strip().split('\n')
            intent = None
            confidence = None
            
            for line in lines:
                line = line.strip()
                if line.startswith('Intent:'):
                    intent = line.split(':', 1)[1].strip()
                elif line.startswith('Confidence:'):
                    try:
                        confidence_str = line.split(':', 1)[1].strip()
                        confidence = float(confidence_str)
                    except (ValueError, IndexError):
                        pass
            
            # Validation de l'intent - nettoyage des caractères invalides
            if intent:
                # Nettoyer les caractères spéciaux comme * ou autres
                intent = intent.replace('*', '').replace('"', '').replace("'", '').strip()
                
                # Vérifier si l'intent est dans la liste disponible
                if available_intents and intent not in available_intents:
                    logger.warning(f"Intent LLM '{intent}' non valide. Mapping vers 'fallback'")
                    intent = 'fallback'
                    confidence = 0.3  # Confiance réduite pour fallback
            
            return intent, confidence
            
        except Exception as e:
            logger.error(f"Erreur parsing réponse LLM: {e}")
            return None, None