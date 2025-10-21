import json
import logging
import time
from typing import Any, Dict, List

from rasa_sdk import Action, Tracker  # type: ignore
from rasa_sdk.executor import CollectingDispatcher  # type: ignore
from rasa_sdk.types import DomainDict  # type: ignore

from src.langchain.planner_chain import generate_analysis_plan_simple

# Configure detailed logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Add console handler if not already present
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


class ActionGenerateVisualization(Action):
    """
    Rasa action that uses the planner chain to generate visualizations and statistics.
    """

    def name(self) -> str:
        return "action_generate_visualization"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[str, Any]]:
        start_time = time.time()
        request_id = f"req_{int(start_time * 1000)}"

        logger.info(f"🚀 [{request_id}] ACTION STARTED: {self.name()}")
        logger.info(f"📧 [{request_id}] Dispatcher type: {type(dispatcher)}")
        logger.info(f"👤 [{request_id}] Tracker type: {type(tracker)}")

        try:
            user_message = tracker.latest_message.get("text", "")
            user_id = tracker.sender_id

            logger.info(f"📝 [{request_id}] User message: '{user_message}'")
            logger.info(f"👤 [{request_id}] User ID: {user_id}")
            logger.info(f"🌍 [{request_id}] LLM Provider: Ollama")

            # Extract entities from Rasa NLU
            entities = tracker.latest_message.get("entities", [])
            extracted_entities = {
                entity["entity"]: entity["value"] for entity in entities
            }

            logger.info(
                f"🔍 [{request_id}] Extracted entities: {json.dumps(extracted_entities, indent=2)}"
            )
            logger.info(
                f"📊 [{request_id}] Full tracker message: {json.dumps(tracker.latest_message, indent=2, default=str)}"
            )

            # Optional language override from Rasa (metadata.language or slot 'language').
            override_language = None
            try:
                meta_any = tracker.latest_message.get("metadata")
                if isinstance(meta_any, dict):
                    meta_dict: Dict[str, Any] = meta_any  # type: ignore[assignment]
                    lang_meta = meta_dict.get("language")
                    if isinstance(lang_meta, str) and lang_meta.strip():
                        override_language = lang_meta
                if override_language is None and hasattr(tracker, "get_slot"):
                    slot_lang = tracker.get_slot("language")  # type: ignore[attr-defined]
                    if isinstance(slot_lang, str) and slot_lang.strip():
                        override_language = slot_lang
            except Exception as lang_exc:
                logger.warning(
                    f"⚠️  [{request_id}] Language detection error: {lang_exc}"
                )

            logger.info(f"🌐 [{request_id}] Language: {override_language or 'auto'}")

            # Normalize language
            if isinstance(override_language, str):
                override_language = override_language.split("-")[0].lower() or None

            logger.info(f"⚙️  [{request_id}] Starting LLM plan generation...")
            plan_start = time.time()

            # If no override, planner will run in auto language detection mode (pass None)
            plan_obj = generate_analysis_plan_simple(
                user_message,
                {},  # Empty entities for now
            )

            plan_time = time.time() - plan_start
            logger.info(f"✅ [{request_id}] LLM plan generated in {plan_time:.2f}s")
            logger.info(f"📋 [{request_id}] Plan object type: {type(plan_obj)}")

            # Serialize plan (Pydantic model) to JSON and return as single message
            try:
                if hasattr(plan_obj, "model_dump_json"):
                    plan_json = plan_obj.model_dump_json(indent=2)  # type: ignore[attr-defined]
                    logger.info(
                        f"✅ [{request_id}] Plan serialized using model_dump_json"
                    )
                else:
                    plan_json = json.dumps(plan_obj, indent=2, default=str)
                    logger.info(f"✅ [{request_id}] Plan serialized using json.dumps")

                logger.info(
                    f"📄 [{request_id}] Plan JSON length: {len(plan_json)} characters"
                )
                logger.debug(
                    f"📄 [{request_id}] Plan JSON preview: {plan_json[:500]}..."
                )

            except Exception as ser_exc:
                logger.error(f"❌ [{request_id}] Serialization error: {ser_exc}")
                plan_json = f"Serialization error: {ser_exc}"

            logger.info(f"📤 [{request_id}] Sending response via dispatcher...")
            # Convertir le JSON string en objet Python si nécessaire
            try:
                if isinstance(plan_json, str):
                    chart_data = json.loads(plan_json)
                else:
                    chart_data = plan_json
                
                # Envoyer avec le format custom pour les graphiques
                dispatcher.utter_message(
                    text="Voici votre visualisation :",
                    custom=self._convert_to_nextjs_format(chart_data)
                )
            except json.JSONDecodeError:
                # Fallback si problème de parsing JSON
                dispatcher.utter_message(text=plan_json)
            logger.info(f"✅ [{request_id}] Response sent successfully")

            total_time = time.time() - start_time
            logger.info(f"🏁 [{request_id}] ACTION COMPLETED in {total_time:.2f}s")

        except Exception as e:
            error_msg = f"Error generating visualization: {str(e)}"
            logger.error(f"💥 [{request_id}] ACTION ERROR: {error_msg}")
            logger.exception(f"💥 [{request_id}] Full exception details:")

            try:
                logger.info(f"📤 [{request_id}] Sending error response...")
                dispatcher.utter_message(text="❌ Error generating visualization.")
                dispatcher.utter_message(text=error_msg)
                logger.info(f"✅ [{request_id}] Error response sent")
            except Exception as dispatch_err:
                logger.error(
                    f"💥 [{request_id}] Failed to send error response: {dispatch_err}"
                )

        logger.info(f"🔚 [{request_id}] Returning from action...")
    def _convert_to_nextjs_format(self, chart_data: dict) -> dict:
        """Convertit les données au format Next.js"""
        nextjs_data = {
            "linePlots": [],
            "boxPlots": []
        }
        
        if 'charts' in chart_data:
            for chart in chart_data['charts']:
                # Extraire les catégories
                categories = self._extract_categories(chart)
                
                # Créer les séries
                series = []
                for metric in chart.get('metrics', []):
                    # 🚨 IMPORTANT: Récupérer les vraies données
                    values = self._get_actual_metric_values(metric, categories)
                    series.append({
                        "label": metric.get('title', f"Série {len(series) + 1}"),
                        "values": values
                    })
                
                line_plot = {
                    "chartTitle": chart.get('title', 'Graphique'),
                    "xAxisLabel": self._get_x_axis_label(chart),
                    "yAxisLabel": self._get_y_axis_label(chart),
                    "bins": categories,
                    "series": series
                }
                nextjs_data["linePlots"].append(line_plot)
        
        # Nettoyer les listes vides
        if not nextjs_data["boxPlots"]:
            del nextjs_data["boxPlots"]
        
        return nextjs_data
    
    def _extract_categories(self, chart: dict) -> list:
        """Extrait les catégories pour l'axe X"""
        categories = []
        for metric in chart.get('metrics', []):
            for group in metric.get('group_by', []):
                categories.extend(group.get('categories', []))
        
        # Supprimer doublons
        unique_categories = []
        for cat in categories:
            if cat not in unique_categories:
                unique_categories.append(cat)
        
        return unique_categories if unique_categories else ['Catégorie 1', 'Catégorie 2']
    
    def _get_actual_metric_values(self, metric: dict, categories: list) -> list:
        """🚨 CRITIQUE: Récupère les vraies données métier"""
        # TODO: Implémenter selon votre source de données
        # Exemples d'implémentation :
        
        # Option 1: Base de données
        # return self._query_database(metric, categories)
        
        # Option 2: API externe  
        # return self._fetch_from_api(metric, categories)
        
        # Option 3: Fichier de données
        # return self._load_from_file(metric, categories)
        
        # 🚨 TEMPORAIRE: Valeurs de test (REMPLACER PAR VOS DONNÉES)
        import random
        return [random.uniform(20, 100) for _ in categories]
    
    def _get_x_axis_label(self, chart: dict) -> str:
        """Génère le label de l'axe X"""
        first_metric = chart.get('metrics', [{}])[0]
        first_group = first_metric.get('group_by', [{}])[0]
        categories = first_group.get('categories', [])
        
        if any('MALE' in str(cat) or 'FEMALE' in str(cat) for cat in categories):
            return 'Sexe'
        elif any('ISCHEMIC' in str(cat) or 'HEMORRHAGE' in str(cat) for cat in categories):
            return "Type d'AVC"
        else:
            return 'Catégories'
    
    def _get_y_axis_label(self, chart: dict) -> str:
        """Génère le label de l'axe Y"""
        first_metric = chart.get('metrics', [{}])[0]
        metric_name = first_metric.get('metric', 'Valeurs')
        
        metric_labels = {
            'DTN': 'Temps DTN (minutes)',
            'NIHSS': 'Score NIHSS',
            'AGE': 'Âge (années)',
            'BP': 'Pression Artérielle (mmHg)'
        }
        
        return metric_labels.get(metric_name, metric_name)

        return []
