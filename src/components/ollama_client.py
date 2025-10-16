"""
Ollama client for LLM Intent Router.
Standalone client for communication with the Ollama API.
Supports centralized configuration and environment variables.
"""

import logging
from typing import List, Optional, Tuple

import requests

# Import the centralized config manager if available
try:
    from src.config.llm_config_manager import get_llm_config_manager
except ImportError:
    # Fallback if the module is not accessible
    get_llm_config_manager = None

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for the Ollama API with centralized configuration"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        use_centralized_config: bool = True,
    ):
        """
        Initialize the Ollama client

        Args:
            base_url: Ollama URL (override centralized config if provided)
            model: Model to use (override centralized config if provided)
            timeout: Timeout in seconds (override centralized config if provided)
            use_centralized_config: Use centralized configuration
        """
        # Load configuration from centralized manager if enabled
        if use_centralized_config and get_llm_config_manager:
            try:
                config_manager = get_llm_config_manager()
                client_config = config_manager.get_effective_model_for_ollama_client()

                # Utiliser les valeurs de la config centralisée sauf si overridées
                self.base_url = (base_url or client_config["base_url"]).rstrip("/")
                self.model = model or client_config["model"]
                self.timeout = timeout or client_config["timeout"]
                self.max_retries = client_config.get("max_retries", 3)
                self.fallback_models = client_config.get("fallback_models", [])
                self.model_config = client_config.get("model_config", {})

                logger.info(f"Centralized configuration loaded - Model: {self.model}")

            except Exception as e:
                logger.warning(
                    f"Error loading centralized config: {e}, using default values"
                )
                self._set_default_values(base_url, model, timeout)
        else:
            # Manual configuration or fallback
            self._set_default_values(base_url, model, timeout)

        logger.info(f"OllamaClient initialized: {self.base_url}, model: {self.model}")

    def _set_default_values(
        self, base_url: Optional[str], model: Optional[str], timeout: Optional[int]
    ):
        """Set default values"""
        self.base_url = (base_url or "http://ollama:11434").rstrip("/")
        self.model = model or "llama3.1:8b"
        self.timeout = timeout or 30
        self.max_retries = 3
        self.fallback_models = ["llama3.1:8b", "tinyllama"]
        self.model_config = {
            "temperature": 0.1,
            "num_predict": 10,
            "stop_sequences": ["\n", ".", ",", ":", ";"],
        }

    def health_check(self) -> bool:
        """Check if Ollama is accessible"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    def classify_intent(
        self, user_message: str, available_intents: List[str]
    ) -> Tuple[Optional[str], Optional[float]]:
        """Classify an intent with Ollama using centralized configuration"""
        try:
            # Get the prompt template from the configuration
            prompt = self._get_optimized_prompt(user_message, available_intents)

            # Prepare model options from the configuration
            model_options = {
                "temperature": self.model_config.get("temperature", 0.1),
                "num_predict": self.model_config.get(
                    "num_predict", 10
                ),  # Ollama uses num_predict
                "stop": self.model_config.get(
                    "stop_sequences", ["\n", ".", ",", ":", ";"]
                ),
            }

            # Prepare the request payload
            data = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": model_options,
            }

            # Send the request with retry if configured
            response = self._send_request_with_retry(data)

            if not response:
                return None, 0.0

            result = response.json()
            llm_response = result.get("response", "").strip()

            # Parse the response
            intent, confidence = self._parse_simple_response(
                llm_response, available_intents
            )

            if intent and confidence is not None:
                logger.debug(f"Classification succeeded: {intent} ({confidence})")
                return intent, confidence
            else:
                logger.warning(f"Impossible to parse response: '{llm_response}'")
                return None, 0.0

        except Exception as e:
            logger.error(f"Error classifying with Ollama: {e}")
            return None, 0.0

    def _get_optimized_prompt(
        self, user_message: str, available_intents: List[str]
    ) -> str:
        """Generate an optimized prompt based on model configuration"""
        # Get the template from centralized configuration
        if get_llm_config_manager:
            try:
                config_manager = get_llm_config_manager()
                template_name = self.model_config.get(
                    "prompt_template", "optimized_multilingual"
                )
                template = config_manager.get_prompt_template(template_name)

                return template.format(
                    user_message=user_message,
                    available_intents=", ".join(available_intents),
                )
            except Exception as e:
                logger.warning(f"Error retrieving template: {e}")

        # Default template if there's an issue with the configuration
        return f"""You are an expert intent classifier that understands multiple languages.

Task: Classify the user message into ONE of the given categories.
Message: "{user_message}"
Available categories: {", ".join(available_intents)}

Rules:
- Respond with ONLY the category name
- Understand French, English, and other languages
- "Bonjour", "Salut", "Hello", "Hi" → greet
- "Au revoir", "Goodbye", "Bye" → goodbye
- No explanation needed

Classification:"""

    def _send_request_with_retry(self, data) -> Optional[requests.Response]:
        """Send the request with retry according to the configuration"""
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/api/generate", json=data, timeout=self.timeout
                )

                if response.status_code == 200:
                    return response
                else:
                    logger.warning(
                        f"Attempt {attempt + 1}: Status {response.status_code}"
                    )

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")

            # Wait before retry (except last attempt)
            if attempt < self.max_retries - 1:
                import time

                time.sleep(1.0)

        logger.error(f"All {self.max_retries} attempts failed")
        return None

    def _parse_simple_response(
        self, llm_response: str, available_intents: List[str]
    ) -> Tuple[Optional[str], Optional[float]]:
        """Parse the LLM response examples to extract intent"""
        try:
            # Clean the response
            response = llm_response.strip().lower()

            # Expected format: "-> intent" or just "intent"
            if response.startswith("->"):
                response = response[2:].strip()

            # Search for the exact intent in the response
            for intent in available_intents:
                if intent.lower() == response or response.startswith(intent.lower()):
                    return intent, 0.8

            # If no intent found, try to parse the words
            words = response.split()
            if words:
                first_word = words[0].strip(',:."')
                for intent in available_intents:
                    if intent.lower() == first_word:
                        return intent, 0.8

            # Fallback if nothing found
            logger.debug(f"No intent found in: '{response}'")
            return None, None

        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return None, None
