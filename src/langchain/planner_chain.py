import logging
from typing import Any, Dict, List, Type

# Fix LangChain compatibility issue
try:
    import langchain

    if not hasattr(langchain, "verbose"):
        langchain.verbose = False  # type: ignore
    if not hasattr(langchain, "debug"):
        langchain.debug = False  # type: ignore
    if not hasattr(langchain, "llm_cache"):
        langchain.llm_cache = None  # type: ignore
except ImportError:
    pass

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_ollama import ChatOllama

from src import env
from src.langchain.planner_examples import get_few_shot_examples
from src.langchain.planner_schema import AnalysisPlan

logger = logging.getLogger(__name__)


def create_llm() -> ChatOllama:
    """Create Ollama LLM instance."""
    base_url, model = env.get_ollama_config()
    logger.info(f"Creating Ollama LLM with base_url={base_url}, model={model}")
    return ChatOllama(
        model=model,
        base_url=base_url,
        temperature=0,
    )


# Initialize the LLM using the factory (lazy initialization)
llm: ChatOllama | None = None


def get_llm() -> ChatOllama:
    """Get or create the LLM instance."""
    global llm
    # Always recreate LLM to pick up configuration changes
    llm = create_llm()
    return llm


# --- SCHEMA INJECTION UTILITY ---
def get_schema_description(model: Type[Any]) -> str:
    """
    Recursively extract field descriptions from a Pydantic model as a readable schema spec (Pydantic v2 compatible).
    """
    from typing import get_args, get_origin

    def describe(model: Type[Any], indent: int = 0) -> str:
        lines: List[str] = []
        if hasattr(model, "model_fields"):
            for name, field in model.model_fields.items():
                desc = field.description or field.title or ""
                typ = str(field.annotation)
                lines.append(" " * indent + f"- {name} ({typ}): {desc}")
                # Recurse for nested models
                outer = get_origin(field.annotation)
                inner = get_args(field.annotation)
                if (
                    outer in (list, List)
                    and inner
                    and hasattr(inner[0], "model_fields")
                ):
                    lines.append(describe(inner[0], indent + 2))
                elif hasattr(field.annotation, "model_fields"):
                    lines.append(describe(field.annotation, indent + 2))
        return "\n".join(lines)

    return f"AnalysisPlan schema:\n{describe(model)}"


SCHEMA_DESCRIPTION: str = get_schema_description(AnalysisPlan)

# Step 1: Chain-of-Thought reasoning step (no context)
cot_prompt: ChatPromptTemplate = ChatPromptTemplate.from_messages(  # type: ignore
    [
        (
            "system",
            "You are a clinical analytics planner. User interface language: {language}. Think step by step about how to answer the user's query, considering all entities. Explain your reasoning in detail in English (for internal clarity) even if the user language is different. Do not output the plan yet.",
        ),
        ("user", "USER_UTTERANCE:\n{question}\n\nENTITIES_DETECTED(JSON):\n{entities}"),
    ]
)

few_shot_examples = get_few_shot_examples()


def _build_few_shots_text() -> str:
    parts: List[str] = []
    for idx, ex in enumerate(few_shot_examples, start=1):
        parts.append(
            "\n".join(
                [
                    f"EXAMPLE {idx}:",
                    f"Description: {ex['description']}",
                    "User Message:",
                    ex["user"],
                    "Assistant Plan JSON:",
                    ex["assistant"],
                    "---",
                ]
            )
        )
    return "\n".join(parts)


FEW_SHOTS_TEXT = _build_few_shots_text()

# Step 2: Structured plan generation prompt with single few_shots variable
plan_prompt: ChatPromptTemplate = ChatPromptTemplate.from_messages(  # type: ignore
    [
        (
            "system",
            "You are a planner. Interface language: {language}. Produce ONLY a valid AnalysisPlan JSON according to the schema. "
            "All 'title' and 'description' fields MUST be written in the interface language ({language}). "
            "Keep enum-like codes (metric, chart_type, test_type, stroke categories, sex categories) in their canonical uppercase English forms. "
            "Use the reasoning and prior examples. Place detected entities into metrics (group_by / filters). "
            "Prefer LINE/BAR for trends or comparisons; BOX/VIOLIN/HISTOGRAM for distributions.",
        ),
        ("system", "SCHEMA:\n" + SCHEMA_DESCRIPTION),
        ("system", "FEW_SHOT_EXAMPLES:\n{few_shots}"),
        (
            "system",
            "REASONING (English internal reasoning shown below can differ from output language):\n{reasoning}",
        ),
        ("user", "USER_UTTERANCE:\n{question}\n\nENTITIES_DETECTED(JSON):\n{entities}"),
    ]
)


def get_chains() -> tuple[Any, Any, Any]:
    """Get the chains (cot_chain, plan_chain, full_chain) with the current LLM."""
    current_llm = get_llm()

    # Use regular LLM instead of structured output for better Ollama compatibility
    plan_prompt_json = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a planner. Interface language: {language}. Produce ONLY a valid AnalysisPlan JSON according to the schema. "
                "All 'title' and 'description' fields MUST be written in the interface language ({language}). "
                "Keep enum-like codes (metric, chart_type, test_type, stroke categories, sex categories) in their canonical uppercase English forms. "
                "Use the reasoning and prior examples. Place detected entities into metrics (group_by / filters). "
                "Prefer LINE/BAR for trends or comparisons; BOX/VIOLIN/HISTOGRAM for distributions. "
                "Return ONLY the JSON object, no additional text or formatting.",
            ),
            ("system", "SCHEMA:\n" + SCHEMA_DESCRIPTION),
            ("system", "FEW_SHOT_EXAMPLES:\n{few_shots}"),
            (
                "system",
                "REASONING (English internal reasoning shown below can differ from output language):\n{reasoning}",
            ),
            (
                "user",
                "USER_UTTERANCE:\n{question}\n\nENTITIES_DETECTED(JSON):\n{entities}",
            ),
        ]
    )

    # Compose the chain: CoT -> Plan
    cot_chain = cot_prompt | current_llm
    plan_chain = plan_prompt_json | current_llm

    full_chain = (
        RunnablePassthrough.assign(
            reasoning=lambda x: cot_chain.invoke(
                {
                    "question": x["question"],
                    "entities": x["entities"],
                    "language": x.get("language", "auto"),
                }
            )
        )
        | plan_chain
    )

    return cot_chain, plan_chain, full_chain


def _detect_chart_type_from_query(query: str) -> str | None:
    """
    Detect explicit chart type mentions in user query.
    Returns the chart type if explicitly mentioned, None otherwise.
    Supports English and French.
    """
    query_lower = query.lower()

    # Chart type patterns (English and French)
    chart_patterns = {
        "BAR": [
            "bar chart",
            "bar graph",
            "barchart",
            "barres",
            "graphique en barres",
            "diagramme en barres",
        ],
        "LINE": [
            "line chart",
            "line graph",
            "linechart",
            "courbe",
            "ligne",
            "graphique linéaire",
            "graphe linéaire",
        ],
        "PIE": [
            "pie chart",
            "pie graph",
            "camembert",
            "circulaire",
            "tarte",
            "diagramme circulaire",
        ],
        "BOX": [
            "box plot",
            "boxplot",
            "box-plot",
            "boîte à moustaches",
            "boite a moustaches",
            "box and whisker",
        ],
        "SCATTER": [
            "scatter plot",
            "scatterplot",
            "scatter",
            "nuage de points",
            "dispersion",
        ],
        "HISTOGRAM": ["histogram", "histogramme", "histogramm", "distribution"],
        "RADAR": [
            "radar chart",
            "spider chart",
            "radar",
            "toile d'araignée",
            "toile",
            "araignée",
        ],
        "AREA": ["area chart", "area graph", "aire", "graphique en aire", "surface"],
        "WATERFALL": [
            "waterfall",
            "cascade",
            "waterfall chart",
            "diagramme en cascade",
        ],
    }

    # Check for each chart type
    for chart_type, patterns in chart_patterns.items():
        for pattern in patterns:
            if pattern in query_lower:
                return chart_type

    return None


def generate_analysis_plan_simple(question: str, entities: Dict[str, Any]) -> Any:
    """
    Simplified generation for Ollama - parse JSON manually instead of using structured output.
    """
    import json
    import logging

    from pydantic import ValidationError

    logger = logging.getLogger(__name__)

    # Prepare inputs
    entities_json = json.dumps(entities)
    language = "auto"

    # Get LLM and build prompt
    llm = get_llm()

    # Simple prompt for JSON generation
    prompt_text = f"""You are a clinical analytics planner. Produce ONLY a valid AnalysisPlan JSON according to the schema.

CRITICAL: CHART TYPE SELECTION - READ THE USER REQUEST CAREFULLY!

When the user explicitly mentions a chart type (e.g., "bar chart", "pie chart", "line graph", etc.), 
YOU MUST use that exact chart type in the JSON output.

Chart type keywords to detect:
- "bar chart", "bar graph", "barres" → use "BAR"
- "line chart", "line graph", "courbe", "ligne" → use "LINE"  
- "pie chart", "camembert", "circular" → use "PIE"
- "box plot", "boîte à moustaches", "box-and-whisker" → use "BOX"
- "scatter plot", "nuage de points", "scatter" → use "SCATTER"
- "histogram", "histogramme", "distribution" → use "HISTOGRAM"
- "radar chart", "spider chart", "radar" → use "RADAR"
- "area chart", "aire", "area" → use "AREA"

RULES FOR AUTOMATIC SELECTION (when user doesn't specify):
- Use LINE or AREA for trends over time or continuous data
- Use BAR for categorical comparisons between groups
- Use PIE for showing proportions/percentages of a whole
- Use BOX for showing data distribution and outliers
- Use HISTOGRAM for frequency distributions
- Use SCATTER for showing correlation between two variables
- Use RADAR for multi-dimensional comparisons

SCHEMA:
{SCHEMA_DESCRIPTION}

FEW_SHOT_EXAMPLES:
{FEW_SHOTS_TEXT}

USER_UTTERANCE:
{question}

ENTITIES_DETECTED(JSON):
{entities_json}

IMPORTANT: Analyze the USER_UTTERANCE above for chart type keywords. If the user says "show me a [TYPE] chart", 
use that TYPE in your chart_type field. Generate a valid JSON response for AnalysisPlan. Return ONLY the JSON object, no additional text."""

    try:
        # Get response from LLM
        logger.info(
            f"[LLM_REQUEST] Sending prompt to LLM (length: {len(prompt_text)} chars)"
        )
        response = llm.invoke(prompt_text)

        # Extract text content
        if hasattr(response, "content"):
            json_text = response.content.strip()
        else:
            json_text = str(response).strip()

        logger.info(
            f"[LLM_RESPONSE] Received response (length: {len(json_text)} chars)"
        )
        logger.info(f"[LLM_RESPONSE] First 300 chars: {json_text[:300]}...")

        # Show full response if it's short (likely an error or incomplete)
        if len(json_text) < 500:
            logger.warning(
                f"[LLM_RESPONSE] Response is suspiciously short! Full response:\n{json_text}"
            )

        # Find JSON in response (handle cases where LLM adds extra text)
        start_idx = json_text.find("{")
        end_idx = json_text.rfind("}")

        logger.info(f"[JSON_PARSE] JSON boundaries: start={start_idx}, end={end_idx}")

        if start_idx != -1 and end_idx != -1:
            json_only = json_text[start_idx : end_idx + 1]
            logger.info(f"[JSON_PARSE] Extracted JSON (length: {len(json_only)} chars)")

            # Parse JSON
            parsed_json = json.loads(json_only)
            logger.info("[JSON_PARSE] Parsed JSON successfully")

            # FALLBACK: Override chart_type if user explicitly mentioned one in the query
            # This ensures the user's explicit request is honored even if LLM doesn't follow instructions
            detected_chart_type = _detect_chart_type_from_query(question)
            logger.info(
                f"[CHART_TYPE_DETECT] Detected type from query: {detected_chart_type}"
            )

            if (
                detected_chart_type
                and "charts" in parsed_json
                and parsed_json["charts"]
            ):
                for chart in parsed_json["charts"]:
                    original_type = chart.get("chart_type", "UNKNOWN")
                    chart["chart_type"] = detected_chart_type
                    if original_type != detected_chart_type:
                        logger.warning(
                            f"[CHART_TYPE_OVERRIDE] User requested '{detected_chart_type}' but LLM generated '{original_type}'. "
                            f"Overriding to user's explicit request."
                        )

            # Log chart types generated by LLM
            if "charts" in parsed_json and parsed_json["charts"]:
                for idx, chart in enumerate(parsed_json["charts"]):
                    chart_type = chart.get("chart_type", "UNKNOWN")
                    chart_title = chart.get("title", "N/A")
                    logger.info(
                        f"[LLM_OUTPUT] Chart {idx + 1}: type='{chart_type}', title='{chart_title}'"
                    )
            else:
                logger.warning("[LLM_OUTPUT] No charts found in LLM response")

            # Return raw JSON directly - skip Pydantic validation for Ollama compatibility
            logger.info("Returning raw JSON (skipping Pydantic validation for Ollama)")
            return parsed_json

        else:
            logger.error("No valid JSON found in response")
            raise ValueError("No valid JSON found in LLM response")

    except Exception as e:
        logger.error(f"Error in generate_analysis_plan_simple: {e}")
        logger.exception("Full traceback:")

        # Detect chart type from user query even in fallback
        detected_chart_type = _detect_chart_type_from_query(question)
        fallback_chart_type = detected_chart_type if detected_chart_type else "BAR"

        logger.warning(
            f"[FALLBACK] Using fallback plan with chart type: {fallback_chart_type}"
        )

        # Return a fallback simple plan
        fallback = {
            "charts": [
                {
                    "title": "Simple Chart",
                    "description": f"Chart for: {question}",
                    "chart_type": fallback_chart_type,
                    "metrics": [
                        {
                            "title": "Simple Metric",
                            "description": "Basic metric",
                            "metric": "DTN",
                            "group_by": None,
                            "filters": None,
                        }
                    ],
                }
            ],
            "statistical_tests": None,
        }
        return fallback
    """
    Generate a validated AnalysisPlan from user input, with chain-of-thought reasoning and automatic correction/retry on validation failure.
    If debug=True, returns a dict with all prompts, LLM responses, validation attempts, and the final output.
    Always includes 'reasoning' in the debug output, even if an error occurs.
    """
    import json
    import logging

    logger = logging.getLogger(__name__)

    # Language handling: if caller passes None or 'auto', let the model infer from user utterance.
    if not language:
        language = "auto"

    input_dict: Dict[str, Any] = {
        "question": question,
        "entities": json.dumps(entities),
        "few_shots": FEW_SHOTS_TEXT,
        "language": language,
    }
    logger.info(f"[Planner] input_dict: {input_dict}")

    # Get the chains
    cot_chain, plan_chain, full_chain = get_chains()
    _chain: Any = full_chain

    steps: List[Any] = []
    attempts: List[Any] = []
    reasoning: Any = None
    # --- Chain-of-Thought step ---
    cot_inputs: Dict[str, Any] = {
        "question": question,
        "entities": json.dumps(entities),
        "language": language,
    }
    logger.info(f"[Planner] cot_inputs: {cot_inputs}")
    try:
        cot_prompt_rendered: str = cot_prompt.format_prompt(**cot_inputs).to_string()
        logger.info(f"[Planner] cot_prompt_rendered: {cot_prompt_rendered}")
        cot_response: Any = cot_chain.invoke(cot_inputs)
        logger.info(f"[Planner] cot_response: {cot_response}")
        steps.append(
            {
                "step": "chain_of_thought",
                "prompt": cot_prompt_rendered,
                "response": cot_response,
            }
        )
        reasoning = cot_response
    except Exception as cot_exc:
        logger.error(f"[Planner] COT Exception: {cot_exc}")
        steps.append(
            {
                "step": "chain_of_thought",
                "prompt": cot_prompt.format_prompt(**cot_inputs).to_string(),
                "response": f"ERROR: {cot_exc}",
            }
        )
        reasoning = f"ERROR: {cot_exc}"
    # --- Plan generation and correction loop ---
    plan_inputs: Dict[str, Any] = {
        "question": question,
        "entities": json.dumps(entities),
        "reasoning": reasoning,
        "few_shots": FEW_SHOTS_TEXT,
        "language": language,
    }
    logger.info(f"[Planner] plan_inputs: {plan_inputs}")
    plan_prompt_rendered: str = plan_prompt.format_prompt(**plan_inputs).to_string()
    logger.info(f"[Planner] plan_prompt_rendered: {plan_prompt_rendered}")
    for attempt in range(max_retries + 1):
        try:
            logger.info(
                f"[Planner] Attempt {attempt + 1}: invoking _chain with input_dict: {input_dict}"
            )
            result: Any = _chain.invoke(input_dict)
            logger.info(f"[Planner] Attempt {attempt + 1}: result: {result}")
            steps.append(
                {
                    "step": f"plan_attempt_{attempt + 1}",
                    "prompt": plan_prompt_rendered,
                    "response": result,
                }
            )
            if debug:
                return {
                    "reasoning": reasoning,
                    "steps": steps,
                    "attempts": attempts,
                    "final_output": result,
                }
            return result
        except ValidationError as ve:
            logger.error(f"[Planner] ValidationError: {ve}")
            attempts.append(
                {
                    "error": str(ve),
                    "input": input_dict,
                    "output": ve.json() if hasattr(ve, "json") else str(ve),
                }
            )
            if attempt == max_retries:
                if debug:
                    return {
                        "reasoning": reasoning,
                        "steps": steps,
                        "attempts": attempts,
                        "final_output": None,
                    }
                raise
            # --- Correction/self-critique step ---
            invalid_output: str = ve.json() if hasattr(ve, "json") else str(ve)
            critique_prompt_obj: ChatPromptTemplate = ChatPromptTemplate.from_messages(  # type: ignore
                [
                    (
                        "system",
                        "The following output did not pass validation. Critique the output, explain what is wrong, and then return a corrected valid AnalysisPlan JSON. Only fix the error described.",
                    ),
                    (
                        "user",
                        f"Original user input: {input_dict}\n\nInvalid output: {invalid_output}\n\nValidation error: {str(ve)}",
                    ),
                ]
            )
            critique_prompt_rendered: str = (
                critique_prompt_obj.format_prompt().to_string()
            )
            logger.info(
                f"[Planner] critique_prompt_rendered: {critique_prompt_rendered}"
            )
            critique_chain: Any = (
                critique_prompt_obj | create_llm().with_structured_output(AnalysisPlan)
            )
            critique_response: Any = critique_chain.invoke({})
            logger.info(f"[Planner] critique_response: {critique_response}")
            steps.append(
                {
                    "step": f"correction_attempt_{attempt + 1}",
                    "prompt": critique_prompt_rendered,
                    "response": critique_response,
                }
            )
            _chain = critique_chain
