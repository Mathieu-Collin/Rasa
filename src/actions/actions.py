import json
import logging
from typing import Any, Dict, List, cast

import pandas as pd

from src.actions.long_action.long_action import LongAction
from src.actions.long_action.long_action_context import LongActionContext
from src.domain.dto.analytics.hospital_comparison import (
    ComparisonTestDTO,
    HospitalComparisonResult,
    HospitalDatasetInfo,
    ShapiroTestDTO,
)
from src.domain.langchain import schema as lang_schema
from src.executors import plan_executor
from src.executors.graphql.client import GraphQLProxyClient
from src.executors.hospital_comparison.hospital_statistics import HospitalStatistics
from src.executors.langchain import pipeline as lang_pipeline
from src.executors.simple_planner import HeuristicVisualizationPlanner
from src.shared import ssot_loader

logger = logging.getLogger(__name__)

try:
    ssot_loader.validate_metric_metadata_complete(logger)
except Exception as _e:
    logger.debug("SSOT validation skipped due to: %s", _e)


class ActionGenerateVisualization(LongAction):
    """Long action that uses the planner chain to generate visualizations and statistics.

    In callback mode this streams messages via the long-action callback URL;
    otherwise it behaves like a normal synchronous action and uses the
    dispatcher directly.
    """

    def name(self) -> str:
        return "action_generate_visualization"

    async def work(self, ctx: LongActionContext) -> Any:
        try:
            user_message = ctx.text
            session_token = ctx.sender_id
            logger.info("Processing visualization request: '%s'", user_message)

            latest_meta = ctx.metadata

            latest_any = ctx.tracker_snapshot.get("latest_message")
            entities_list: List[Dict[str, Any]] = []
            if isinstance(latest_any, dict):
                latest_msg = cast(Dict[str, Any], latest_any)
                ents_any = latest_msg.get("entities", [])
                if isinstance(ents_any, list):
                    ents_list = cast(List[Any], ents_any)
                    for e_any in ents_list:
                        if isinstance(e_any, dict):
                            entities_list.append(cast(Dict[str, Any], e_any))
            extracted_entities: Dict[str, Any] = {ent["entity"]: ent["value"] for ent in entities_list if isinstance(ent.get("entity"), str) and "value" in ent}

            override_language: Any = None
            try:
                lang_meta = latest_meta.get("language")
                if isinstance(lang_meta, str) and lang_meta.strip():
                    override_language = lang_meta
                if override_language is None:
                    slot_lang = ctx.slots.get("language")
                    if isinstance(slot_lang, str) and slot_lang.strip():
                        override_language = slot_lang
            except Exception:
                pass
            if isinstance(override_language, str):
                override_language = override_language.split("-")[0].lower() or None

            def progress(msg: str) -> None:
                ctx.say(progress=msg)

            heuristic_plan = HeuristicVisualizationPlanner.try_plan(
                question=user_message,
                entities=extracted_entities,
                language=override_language,
            )

            if heuristic_plan is not None:
                progress("Using simple heuristic plan (no LLM needed)")
                plan_obj: lang_schema.AnalysisPlan = heuristic_plan
            else:
                progress("Calling planner LLM to build a plan")
                plan_obj = lang_pipeline.generate_analysis_plan(
                    question=user_message,
                    entities=extracted_entities,
                    language=override_language,
                    max_retries=2,
                    debug=False,
                    progress_cb=progress,
                )

            visualization = await plan_executor.execute_plan_async(
                plan_obj,
                session_token=session_token,
                max_concurrency=4,
                progress_cb=progress,
            )

            ctx.say(json_message=json.loads(visualization.model_dump_json()))
        except Exception as e:
            error_msg = f"Error generating visualization: {str(e)}"
            logger.error(error_msg)
            ctx.say(text="❌ Error generating visualization.")
            ctx.say(text=error_msg)
        finally:
            ctx.say(text="✅ Visualization generation complete.")
            ctx.done()
        return None


class ActionCompareHospitals(LongAction):
    """Long action for comparing door-to-needle times between two hospitals.

    Performs statistical analysis including:
    - Shapiro-Wilk normality tests
    - T-test or Wilcoxon rank-sum test (depending on normality)
    - Returns structured results with interpretation
    """

    def name(self) -> str:
        return "action_compare_hospitals"

    async def work(self, ctx: LongActionContext) -> Any:
        try:
            user_message = ctx.text
            session_token = ctx.sender_id
            logger.info("Processing hospital comparison request: '%s'", user_message)

            def progress(msg: str) -> None:
                ctx.say(progress=msg)

            progress("Initializing hospital comparison analysis...")

            # Extract hospital IDs from entities
            latest_any = ctx.tracker_snapshot.get("latest_message")
            hospital_1_id = None
            hospital_2_id = None
            
            if isinstance(latest_any, dict):
                latest_msg = cast(Dict[str, Any], latest_any)
                ents_any = latest_msg.get("entities", [])
                if isinstance(ents_any, list):
                    ents_list = cast(List[Any], ents_any)
                    hospital_entities = [e for e in ents_list if isinstance(e, dict) and e.get("entity") == "hospital"]
                    if len(hospital_entities) >= 2:
                        hospital_1_id = hospital_entities[0].get("value")
                        hospital_2_id = hospital_entities[1].get("value")
            
            # For demo/testing: if no hospitals specified, use synthetic data
            if not hospital_1_id or not hospital_2_id:
                progress("No specific hospitals identified, generating demo comparison with synthetic data...")
                analysis_result, dto_result = await self._run_synthetic_comparison(progress)
            else:
                progress(f"Comparing hospitals: {hospital_1_id} vs {hospital_2_id}")
                analysis_result, dto_result = await self._run_real_comparison(
                    hospital_1_id, 
                    hospital_2_id, 
                    session_token, 
                    progress
                )

            # Send structured DTO result for frontend/API consumption
            ctx.say(json_message=json.loads(dto_result.model_dump_json()))
            
            # Send complete detailed summary (same format as original script)
            detailed_summary = analysis_result.get_summary()
            ctx.say(text=detailed_summary)
            
            # Also send the raw dictionary for additional processing
            result_dict = analysis_result.to_dict()
            ctx.say(json_message=result_dict)

        except Exception as e:
            error_msg = f"Error comparing hospitals: {str(e)}"
            logger.error(error_msg, exc_info=True)
            ctx.say(text="❌ Error during hospital comparison.")
            ctx.say(text=error_msg)
        finally:
            ctx.say(text="✅ Hospital comparison complete.")
            ctx.done()
        return None

    async def _run_synthetic_comparison(
        self, 
        progress_cb
    ) -> tuple:
        """Run comparison with synthetic data for demo purposes.
        
        Returns:
            tuple: (AnalysisResult, HospitalComparisonResult)
        """
        progress_cb("Generating synthetic hospital data...")
        
        stats = HospitalStatistics(alpha=0.05)
        analysis_result = stats.run_analysis(n_rows=50, random_state=42)
        
        progress_cb("Running statistical tests...")
        
        # Convert to DTO format
        dto_result = self._convert_to_dto(
            analysis_result,
            hospital_1_id="DEMO_H1",
            hospital_1_name="Demo Hospital 1",
            hospital_2_id="DEMO_H2",
            hospital_2_name="Demo Hospital 2"
        )
        
        return analysis_result, dto_result

        
        # Convert to DTO format
        dto_result = self._convert_to_dto(
            analysis_result,
            hospital_1_id="DEMO_H1",
            hospital_1_name="Demo Hospital 1",
            hospital_2_id="DEMO_H2",
            hospital_2_name="Demo Hospital 2"
        )
        
        return analysis_result, dto_result

    async def _run_real_comparison(
        self,
        hospital_1_id: str,
        hospital_2_id: str,
        session_token: str,
        progress_cb
    ) -> tuple:
        """Run comparison with real data from GraphQL.
        
        Returns:
            tuple: (AnalysisResult, HospitalComparisonResult)
        """
        progress_cb(f"Fetching data for hospital {hospital_1_id}...")
        
        # Fetch data for both hospitals
        # This is a placeholder - you'll need to adapt based on your actual GraphQL schema
        df1 = await self._fetch_hospital_data(hospital_1_id, session_token, progress_cb)
        progress_cb(f"Fetching data for hospital {hospital_2_id}...")
        df2 = await self._fetch_hospital_data(hospital_2_id, session_token, progress_cb)
        
        progress_cb("Running statistical analysis...")
        
        # Run statistical comparison
        stats = HospitalStatistics(alpha=0.05)
        analysis_result = stats.run_analysis_from_dataframes(df1, df2)
        
        # Convert to DTO format
        dto_result = self._convert_to_dto(
            analysis_result,
            hospital_1_id=hospital_1_id,
            hospital_1_name=f"Hospital {hospital_1_id}",
            hospital_2_id=hospital_2_id,
            hospital_2_name=f"Hospital {hospital_2_id}"
        )
        
        return analysis_result, dto_result

    async def _fetch_hospital_data(
        self,
        hospital_id: str,
        session_token: str,
        progress_cb
    ) -> pd.DataFrame:
        """Fetch door-to-needle time data for a hospital from GraphQL.
        
        Returns a DataFrame with columns: door_to_needle, n
        """
        # TODO: Implement actual GraphQL query based on your schema
        # This is a placeholder that returns synthetic data
        progress_cb(f"Querying database for hospital {hospital_id}...")
        
        # Example query structure (adapt to your schema):
        # from src.util.env import get_graphql_url, get_proxy_url
        # graphql_client = GraphQLProxyClient(
        #     proxy_url=get_proxy_url(),
        #     graphql_url=get_graphql_url()
        # )
        # query = '''
        # query GetHospitalDoorToNeedleTimes($hospitalId: String!) {
        #     hospitalMetrics(hospitalId: $hospitalId) {
        #         doorToNeedleTime
        #         count
        #     }
        # }
        # '''
        # result = graphql_client.query(query, session_token, {"hospitalId": hospital_id})
        # if result and result.data:
        #     # Parse result and convert to DataFrame
        #     pass
        return stats.generate_dataset(n_rows=50)

    def _convert_to_dto(
        self,
        analysis_result,
        hospital_1_id: str,
        hospital_1_name: str,
        hospital_2_id: str,
        hospital_2_name: str
    ) -> HospitalComparisonResult:
        """Convert analysis result to DTO format."""
        
        # Build interpretation message
        if analysis_result.is_significant():
            interpretation = (
                f"The analysis shows a SIGNIFICANT difference between {hospital_1_name} "
                f"and {hospital_2_name} (p-value: {analysis_result.test_result.p_value:.4f}). "
                f"The two hospitals show statistically different door-to-needle times."
            )
        else:
            interpretation = (
                f"The analysis shows NO significant difference between {hospital_1_name} "
                f"and {hospital_2_name} (p-value: {analysis_result.test_result.p_value:.4f}). "
                f"The two hospitals show similar door-to-needle times."
            )
        
        # Build summary
        summary = (
            f"Statistical Comparison: {hospital_1_name} vs {hospital_2_name}\n"
            f"Test used: {analysis_result.test_type.upper()}\n"
            f"Sample sizes: {analysis_result.expanded_size_1} vs {analysis_result.expanded_size_2} observations"
        )
        
        return HospitalComparisonResult(
            timestamp=analysis_result.timestamp,
            hospital_1=HospitalDatasetInfo(
                hospital_id=hospital_1_id,
                hospital_name=hospital_1_name,
                sample_size=analysis_result.expanded_size_1,
                shapiro_test=ShapiroTestDTO(
                    statistic=analysis_result.shapiro_hospital_1.statistic,
                    p_value=analysis_result.shapiro_hospital_1.p_value,
                    is_normal=analysis_result.shapiro_hospital_1.is_normal
                )
            ),
            hospital_2=HospitalDatasetInfo(
                hospital_id=hospital_2_id,
                hospital_name=hospital_2_name,
                sample_size=analysis_result.expanded_size_2,
                shapiro_test=ShapiroTestDTO(
                    statistic=analysis_result.shapiro_hospital_2.statistic,
                    p_value=analysis_result.shapiro_hospital_2.p_value,
                    is_normal=analysis_result.shapiro_hospital_2.is_normal
                )
            ),
            comparison_test=ComparisonTestDTO(
                test_type=analysis_result.test_type,
                statistic=(
                    analysis_result.test_result.t_statistic 
                    if analysis_result.test_type == 't-test'
                    else analysis_result.test_result.statistic
                ),
                p_value=analysis_result.test_result.p_value,
                is_significant=analysis_result.is_significant()
            ),
            summary=summary,
            interpretation=interpretation
        )

