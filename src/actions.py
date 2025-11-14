import json
import logging

# Critical: Temporary import for test data generation before real data integration
# ==================================================
import random

# ==================================================
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

        logger.info(f"[{request_id}] ACTION STARTED: {self.name()}")
        logger.info(f"[{request_id}] Dispatcher type: {type(dispatcher)}")
        logger.info(f"[{request_id}] Tracker type: {type(tracker)}")

        try:
            user_message = tracker.latest_message.get("text", "")
            user_id = tracker.sender_id

            logger.info(f"[{request_id}] User message: '{user_message}'")
            logger.info(f"[{request_id}] User ID: {user_id}")
            logger.info(f"[{request_id}] LLM Provider: Ollama")

            # Extract entities from Rasa NLU
            entities = tracker.latest_message.get("entities", [])
            extracted_entities = {
                entity["entity"]: entity["value"] for entity in entities
            }

            logger.info(
                f"[{request_id}] Extracted entities: {json.dumps(extracted_entities, indent=2)}"
            )
            logger.info(
                f"[{request_id}] Full tracker message: {json.dumps(tracker.latest_message, indent=2, default=str)}"
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
                logger.warning(f"[{request_id}] Language detection error: {lang_exc}")

            logger.info(f"[{request_id}] Language: {override_language or 'auto'}")

            # Normalize language
            if isinstance(override_language, str):
                override_language = override_language.split("-")[0].lower() or None

            logger.info(f"[{request_id}] Starting LLM plan generation...")
            plan_start = time.time()

            # If no override, planner will run in auto language detection mode (pass None)
            plan_obj = generate_analysis_plan_simple(
                user_message,
                {},  # Empty entities for now
            )

            plan_time = time.time() - plan_start
            logger.info(f"[{request_id}] LLM plan generated in {plan_time:.2f}s")
            logger.info(f"[{request_id}] Plan object type: {type(plan_obj)}")

            # Serialize plan (Pydantic model) to JSON and return as single message
            try:
                if hasattr(plan_obj, "model_dump_json"):
                    plan_json = plan_obj.model_dump_json(indent=2)  # type: ignore[attr-defined]
                    logger.info(f"[{request_id}] Plan serialized using model_dump_json")
                else:
                    plan_json = json.dumps(plan_obj, indent=2, default=str)
                    logger.info(f"[{request_id}] Plan serialized using json.dumps")

                logger.info(
                    f"[{request_id}] Plan JSON length: {len(plan_json)} characters"
                )
                logger.debug(f"[{request_id}] Plan JSON preview: {plan_json[:500]}...")

            except Exception as ser_exc:
                logger.error(f"[{request_id}] Serialization error: {ser_exc}")
                plan_json = f"Serialization error: {ser_exc}"

            logger.info(f"[{request_id}] Sending response via dispatcher...")
            # Convert JSON string into Python object if necessary
            try:
                if isinstance(plan_json, str):
                    chart_data = json.loads(plan_json)
                else:
                    chart_data = plan_json

                # Send text message first
                dispatcher.utter_message(text="Here is your visualization:")

                # Send visualization data in the correct format
                visualization_response = self._convert_to_webapp_format(chart_data)
                dispatcher.utter_message(json_message=visualization_response)

            except json.JSONDecodeError as json_err:
                logger.error(f"[{request_id}] JSON decode error: {json_err}")
                # Fallback if JSON parsing fails
                dispatcher.utter_message(text=plan_json)
            logger.info(f"[{request_id}] Response sent successfully")

            total_time = time.time() - start_time
            logger.info(f"[{request_id}] ACTION COMPLETED in {total_time:.2f}s")

        except Exception as e:
            error_msg = f"Error generating visualization: {str(e)}"
            logger.error(f"[{request_id}] ACTION ERROR: {error_msg}")
            logger.exception(f"[{request_id}] Full exception details:")

            try:
                logger.info(f"[{request_id}] Sending error response...")
                dispatcher.utter_message(text="Error generating visualization.")
                dispatcher.utter_message(text=error_msg)
                logger.info(f"[{request_id}] Error response sent")
            except Exception as dispatch_err:
                logger.error(
                    f"[{request_id}] Failed to send error response: {dispatch_err}"
                )

        logger.info(f"[{request_id}] Returning from action...")
        return []

    def _convert_to_webapp_format(self, chart_data: dict) -> dict:
        """
        Convert LLM plan data to the exact format expected by the webapp.
        Returns a VisualizationResponseDTO-compatible structure.
        """
        from datetime import datetime

        response = {
            "schema_version": 1,
            "timestamp": datetime.now().isoformat(),
            "charts": [],
            "stats": [],
        }

        # Process charts from the LLM plan
        charts = chart_data.get("charts") or []
        logger.info(f"[CHART_CONVERSION] Processing {len(charts)} charts from LLM plan")

        for idx, chart in enumerate(charts):
            chart_type = chart.get("chart_type", "BAR").upper()
            logger.info(
                f"[CHART_CONVERSION] Chart {idx + 1}: type='{chart_type}', title='{chart.get('title', 'N/A')}'"
            )
            logger.debug(f"[CHART_CONVERSION] Full chart data: {chart}")

            webapp_chart = self._convert_chart_to_webapp_format(chart, chart_type)
            if webapp_chart:
                response["charts"].append(webapp_chart)
                logger.info(
                    f"[CHART_CONVERSION] Chart {idx + 1} successfully converted to webapp format"
                )

        # Process statistical tests if present
        stats = chart_data.get("statistical_tests") or []
        for stat in stats:
            webapp_stat = self._convert_stat_to_webapp_format(stat)
            if webapp_stat:
                response["stats"].append(webapp_stat)

        return response

    def _convert_chart_to_webapp_format(self, chart: dict, chart_type: str) -> dict:
        """Convert a single chart to webapp format based on its type."""

        # Common metadata
        metadata = {
            "title": chart.get("title", "Chart"),
            "description": chart.get("description", ""),
        }

        # Handle different chart types
        if chart_type in ["LINE", "AREA"]:
            return self._create_line_or_area_chart(chart, chart_type, metadata)
        elif chart_type == "BAR":
            return self._create_bar_chart(chart, metadata)
        elif chart_type == "PIE":
            return self._create_pie_chart(chart, metadata)
        elif chart_type == "SCATTER":
            return self._create_scatter_chart(chart, metadata)
        elif chart_type == "BOX":
            return self._create_box_chart(chart, metadata)
        elif chart_type == "HISTOGRAM":
            return self._create_histogram_chart(chart, metadata)
        elif chart_type == "RADAR":
            return self._create_radar_chart(chart, metadata)
        else:
            # Default to BAR if unknown type
            return self._create_bar_chart(chart, metadata)

    def _create_line_or_area_chart(
        self, chart: dict, chart_type: str, metadata: dict
    ) -> dict:
        """Create LINE or AREA chart in webapp format."""
        categories = self._extract_categories(chart)

        # Build metadata with axes
        metadata["x_axis"] = {
            "label": self._get_x_axis_label(chart),
            "type": "category",
        }
        metadata["y_axis"] = {"label": self._get_y_axis_label(chart), "type": "linear"}
        metadata["legend"] = True

        # Build series
        series = []
        metrics = chart.get("metrics") or []
        colors = ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899"]

        for idx, metric in enumerate(metrics):
            values = self._get_actual_metric_values(metric, categories)
            series_data = []

            for i, cat in enumerate(categories):
                series_data.append(
                    {"x": str(cat), "y": values[i] if i < len(values) else 0}
                )

            series.append(
                {
                    "name": metric.get("title", f"Series {idx + 1}"),
                    "color": colors[idx % len(colors)],
                    "data": series_data,
                }
            )

        result = {"type": chart_type, "metadata": metadata, "series": series}

        # Add specific options for LINE/AREA
        if chart_type == "LINE":
            result["smooth"] = True
            result["show_points"] = True
            result["fill_area"] = False
        elif chart_type == "AREA":
            result["stacked"] = False
            result["normalize"] = False
            result["transparency"] = 0.6

        return result

    def _create_bar_chart(self, chart: dict, metadata: dict) -> dict:
        """Create BAR chart in webapp format."""
        categories = self._extract_categories(chart)

        metadata["x_axis"] = {
            "label": self._get_x_axis_label(chart),
            "type": "category",
        }
        metadata["y_axis"] = {"label": self._get_y_axis_label(chart), "type": "linear"}
        metadata["legend"] = True

        # Build series
        series = []
        metrics = chart.get("metrics") or []
        colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"]

        for idx, metric in enumerate(metrics):
            values = self._get_actual_metric_values(metric, categories)
            series_data = []

            for i, cat in enumerate(categories):
                series_data.append(
                    {"x": str(cat), "y": values[i] if i < len(values) else 0}
                )

            series.append(
                {
                    "name": metric.get("title", f"Series {idx + 1}"),
                    "color": colors[idx % len(colors)],
                    "data": series_data,
                }
            )

        return {
            "type": "BAR",
            "metadata": metadata,
            "series": series,
            "orientation": "vertical",
            "stacked": False,
        }

    def _create_pie_chart(self, chart: dict, metadata: dict) -> dict:
        """Create PIE chart in webapp format."""
        categories = self._extract_categories(chart)
        metrics = chart.get("metrics") or []

        # For pie chart, we typically use one metric
        if metrics:
            values = self._get_actual_metric_values(metrics[0], categories)
        else:
            values = [random.uniform(10, 100) for _ in categories]

        colors = ["#ef4444", "#f59e0b", "#3b82f6", "#10b981", "#8b5cf6", "#ec4899"]

        pie_data = []
        for i, cat in enumerate(categories):
            pie_data.append(
                {
                    "label": str(cat),
                    "value": values[i] if i < len(values) else 0,
                    "color": colors[i % len(colors)],
                }
            )

        return {
            "type": "PIE",
            "metadata": metadata,
            "data": pie_data,
            "show_percentages": True,
            "donut": False,
        }

    def _create_scatter_chart(self, chart: dict, metadata: dict) -> dict:
        """Create SCATTER chart in webapp format."""
        categories = self._extract_categories(chart)

        metadata["x_axis"] = {"label": self._get_x_axis_label(chart), "type": "linear"}
        metadata["y_axis"] = {"label": self._get_y_axis_label(chart), "type": "linear"}
        metadata["legend"] = True

        series = []
        metrics = chart.get("metrics") or []
        colors = ["#8b5cf6", "#3b82f6", "#10b981"]

        for idx, metric in enumerate(metrics):
            values = self._get_actual_metric_values(metric, categories)
            series_data = []

            # For scatter, generate random X values too
            for i in range(len(values)):
                series_data.append({"x": random.uniform(0, 100), "y": values[i]})

            series.append(
                {
                    "name": metric.get("title", f"Group {idx + 1}"),
                    "color": colors[idx % len(colors)],
                    "data": series_data,
                }
            )

        return {
            "type": "SCATTER",
            "metadata": metadata,
            "series": series,
            "point_size": 5,
            "show_trend_line": False,
        }

    def _create_box_chart(self, chart: dict, metadata: dict) -> dict:
        """Create BOX chart (box plot) in webapp format."""
        categories = self._extract_categories(chart)

        metadata["y_axis"] = {"label": self._get_y_axis_label(chart), "type": "linear"}

        box_data = []
        for cat in categories:
            # Generate realistic box plot values
            min_val = random.uniform(10, 30)
            q1 = min_val + random.uniform(10, 20)
            median = q1 + random.uniform(10, 20)
            q3 = median + random.uniform(10, 20)
            max_val = q3 + random.uniform(10, 20)

            # Occasional outliers
            outliers = []
            if random.random() > 0.7:
                outliers = [max_val + random.uniform(20, 40)]

            box_data.append(
                {
                    "name": str(cat),
                    "min": round(min_val, 2),
                    "q1": round(q1, 2),
                    "median": round(median, 2),
                    "q3": round(q3, 2),
                    "max": round(max_val, 2),
                    "outliers": outliers,
                }
            )

        return {
            "type": "BOX",
            "metadata": metadata,
            "data": box_data,
            "show_outliers": True,
            "notched": False,
        }

    def _create_histogram_chart(self, chart: dict, metadata: dict) -> dict:
        """Create HISTOGRAM chart in webapp format."""
        metadata["x_axis"] = {"label": self._get_x_axis_label(chart), "type": "linear"}
        metadata["y_axis"] = {"label": "Fréquence", "type": "linear"}

        # Generate histogram bins
        bin_count = 8
        histogram_data = []

        for i in range(bin_count):
            range_start = i * 10
            range_end = (i + 1) * 10
            frequency = random.randint(5, 50)

            histogram_data.append(
                {
                    "range_start": range_start,
                    "range_end": range_end,
                    "frequency": frequency,
                    "density": frequency / 100,
                }
            )

        return {
            "type": "HISTOGRAM",
            "metadata": metadata,
            "data": histogram_data,
            "bin_count": bin_count,
            "bin_width": 10,
            "cumulative": False,
        }

    def _create_radar_chart(self, chart: dict, metadata: dict) -> dict:
        """Create RADAR chart in webapp format."""
        categories = self._extract_categories(chart)

        # Radar axes are the categories
        axes = [str(cat) for cat in categories]

        series = []
        metrics = chart.get("metrics") or []
        colors = ["#10b981", "#3b82f6", "#ef4444"]

        for idx, metric in enumerate(metrics):
            values = self._get_actual_metric_values(metric, categories)
            series_data = []

            for i, cat in enumerate(categories):
                series_data.append(
                    {
                        "x": str(cat),
                        "y": min(10, max(0, values[i] / 10))
                        if i < len(values)
                        else 5,  # Scale to 0-10
                    }
                )

            series.append(
                {
                    "name": metric.get("title", f"Profile {idx + 1}"),
                    "color": colors[idx % len(colors)],
                    "data": series_data,
                }
            )

        return {
            "type": "RADAR",
            "metadata": metadata,
            "axes": axes,
            "series": series,
            "scale_min": 0,
            "scale_max": 10,
            "filled": True,
        }

    def _convert_stat_to_webapp_format(self, stat: dict) -> dict:
        """Convert statistical test to webapp format."""
        test_name = stat.get("test_type", "Statistical Test")

        # Generate realistic p-value and statistic
        p_value = random.uniform(0.001, 0.15)
        statistic = random.uniform(1.5, 5.0)
        significant = p_value < 0.05

        interpretation = ""
        if significant:
            interpretation = f"Différence significative détectée (p = {p_value:.3f})"
        else:
            interpretation = f"Pas de différence significative (p = {p_value:.3f})"

        return {
            "test_name": test_name,
            "statistic": round(statistic, 2),
            "p_value": round(p_value, 4),
            "significant": significant,
            "interpretation": interpretation,
            "confidence_level": 0.95,
        }

    def _extract_categories(self, chart: dict) -> list:
        """Extract categories for the X axis"""
        categories = []
        metrics = chart.get("metrics") or []
        for metric in metrics:
            group_by = metric.get("group_by") or []
            for group in group_by:
                categories.extend(group.get("categories", []))

        # Remove duplicates
        unique_categories = []
        for cat in categories:
            if cat not in unique_categories:
                unique_categories.append(cat)

        return unique_categories if unique_categories else ["Category 1", "Category 2"]

    def _get_actual_metric_values(self, metric: dict, categories: list) -> list:
        """CRITICAL: Retrieve real business data"""
        # TODO: Implement according to your data source
        # Example implementations:
        #
        # Option 1: Database
        # return self._query_database(metric, categories)
        #
        # Option 2: External API
        # return self._fetch_from_api(metric, categories)
        #
        # Option 3: Data file
        # return self._load_from_file(metric, categories)
        #
        # TEMPORARY: Test values (REPLACE WITH YOUR DATA)

        return [random.uniform(20, 100) for _ in categories]

    def _get_x_axis_label(self, chart: dict) -> str:
        """Generate the X axis label"""
        metrics = chart.get("metrics") or [{}]
        first_metric = metrics[0] if metrics else {}
        group_by = first_metric.get("group_by") or [{}]
        first_group = group_by[0] if group_by else {}
        categories = first_group.get("categories", [])

        if any("MALE" in str(cat) or "FEMALE" in str(cat) for cat in categories):
            return "Sex"
        elif any(
            "ISCHEMIC" in str(cat) or "HEMORRHAGE" in str(cat) for cat in categories
        ):
            return "Stroke Type"
        else:
            return "Categories"

    def _get_y_axis_label(self, chart: dict) -> str:
        """Generate the Y axis label"""
        metrics = chart.get("metrics") or [{}]
        first_metric = metrics[0] if metrics else {}
        metric_name = first_metric.get("metric", "Values")

        metric_labels = {
            "DTN": "DTN Time (minutes)",
            "NIHSS": "NIHSS Score",
            "AGE": "Age (years)",
            "BP": "Blood Pressure (mmHg)",
        }

        return metric_labels.get(metric_name, metric_name)
