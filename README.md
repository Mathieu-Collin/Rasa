
# Rasa Action Server for Data Visualization (Ollama-only)

This project provides a Rasa custom action server that generates structured data visualization plans using local LLMs via Ollama. It is designed for privacy, full local control, and easy integration with modern web frontends (e.g., Next.js).

## Overview

**Features:**
- Accepts natural language requests for clinical/statistical visualizations
- Generates structured JSON plans for charts and statistical tests
- Uses only local LLMs via Ollama (no cloud dependencies)
- Supports multiple chart types (bar, line, pie, box, histogram, etc.)
- Fully compatible with Next.js and other modern frontends

## Architecture

```
┌─────────────┐   ┌───────────────┐   ┌─────────────┐
│ Web Client  │→│ Rasa Server    │→│ Ollama LLM   │
│ (Port 4000) │   │ (Port 6055)   │   │ (Port 11434)│
└─────────────┘   └───────────────┘   └─────────────┘
         │
         ▼
   ┌─────────────────────┐
   │ Visualization Plans │
   └─────────────────────┘
```

## Quickstart

### Prerequisites
- Docker & Docker Compose
- Ollama installed and running
- Python 3.10+

### 1. Clone the repository
```bash
git clone <repository-url>
cd rasa-visualization-server
```

### 2. Install and configure Ollama
```bash
# Install Ollama (if not already installed)


# Download the recommended model
ollama pull llama3.2:1b

# Verify Ollama is running
ollama list
```

### 3. Environment configuration
Create or edit your `.env` file:
```env
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:1b
```

### 4. Start the action server
```bash
# In the dev container or local environment
python -m rasa_sdk --actions src.actions

# Or use VS Code task:
# Ctrl+Shift+P > "Tasks: Run Task" > "Start Rasa Actions"
```

The server will be available at `http://localhost:6055`

## API Usage

### Main endpoint
```
POST http://localhost:6055/webhook
Content-Type: application/json
```

### Request format
```json
{
  "next_action": "action_generate_visualization",
  "tracker": {
    "sender_id": "user123",
    "slots": {},
    "latest_message": {
      "text": "Show a bar chart of sales by region",
      "intent": {"name": "generate_chart"},
      "entities": []
    },
    "events": []
  },
  "domain": {}
}
```

### Example requests

#### Bar chart
```json
{
  "text": "Show a bar chart of sales by region"
}
```

#### Line chart
```json
{
  "text": "Show a line chart of revenue over 12 months"
}
```

#### Pie chart
```json
{
  "text": "Show a pie chart of customer age distribution"
}
```

### Response format
```json
{
  "events": [],
  "responses": [{
    "text": "Here is your visualization:",
    "custom": {
      "linePlots": [
        {
          "chartTitle": "Sales by Region",
          "xAxisLabel": "Region",
          "yAxisLabel": "Sales",
          "bins": ["North", "South", "East", "West"],
          "series": [
            {"label": "Sales", "values": [100, 150, 120, 130]}
          ]
        }
      ]
    }
  }]
}
```

## Environment Variables

| Variable         | Description                | Default                |
|------------------|---------------------------|------------------------|
| OLLAMA_BASE_URL  | Ollama server URL         | http://ollama:11434    |
| OLLAMA_MODEL     | Ollama model name         | llama3.2:1b            |

## Recommended Ollama Models

| Model         | Size  | Performance | Use Case           |
|---------------|-------|------------|--------------------|
| llama3.2:1b   | ~1GB  | Fast       | Dev/test           |
| llama3.2:3b   | ~3GB  | Balanced   | Light production   |
| llama3.1:8b   | ~8GB  | High       | Advanced prod      |

## Project Structure

```
├── src/
│   ├── actions.py              # Main Rasa action
│   ├── env.py                  # Ollama config
│   ├── langchain/
│   │   ├── planner_chain.py    # LLM plan generation
│   │   ├── planner_examples.py # Prompt examples
│   │   └── planner_schema.py   # Pydantic schemas
│   └── shared/SSOT/            # Data type definitions
├── .env                        # Environment config
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container setup
├── switch_llm.sh               # Ollama-only config script
└── README.md                   # This file
```

## VS Code Tasks

This project includes VS Code tasks for easy development:

- **Start Rasa Actions**: Runs the action server (`python -m rasa_sdk --actions src.actions`)
- **Switch to Ollama**: Ensures Ollama-only config (`./switch_llm.sh ollama`)

## Docker & Networking

For multi-container setups (Rasa, Actions, Ollama):
- Ensure all containers are on the same Docker network
- Use service names (not IPs) for endpoints (e.g., `http://action:6055/webhook`)
- See `DOCKER_NETWORK_TROUBLESHOOTING.md` for detailed guidance

## Troubleshooting

### Common Issues

- **Connection refused on port 6055**: Make sure the action server is running
- **Ollama not accessible**: Check Ollama container/network config
- **JSON parsing errors**: Ollama may return extra text; the system extracts valid JSON automatically
- **Timeouts**: Use smaller models or increase request timeouts

### Docker Networking

See `DOCKER_NETWORK_TROUBLESHOOTING.md` for step-by-step diagnosis and solutions for container-to-container communication issues.

## Extending & Customization

- Add new chart types: Edit `src/shared/SSOT/ChartType.yml`
- Add new metrics: Edit `src/shared/SSOT/MetricType.yml`
- Add prompt examples: Edit `src/langchain/planner_examples.py`
- Improve LLM prompts: Edit `src/langchain/planner_chain.py`

## Logging & Debugging

Enable detailed logs:
```bash
export PYTHONPATH=/workspace
python -m rasa_sdk --actions src.actions --debug
```

Watch for log messages:
- `Creating Ollama LLM`: Confirms Ollama usage
- `Parsed JSON successfully`: Valid JSON extracted
- `Returning raw JSON`: Ollama compatibility mode

## License

MIT License. See `LICENSE` for details.

## Support

For help:
1. Check logs with `--debug`
2. Test Ollama connectivity
3. See troubleshooting sections above
4. Review `DOCKER_NETWORK_TROUBLESHOOTING.md`

---

**Note:** This project is optimized for Ollama and intentionally avoids cloud dependencies (e.g., OpenAI) for privacy and local control.
ACTION_ENDPOINT_URL=http://172.18.0.6:6055/webhook
