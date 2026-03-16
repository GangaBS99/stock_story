# Agent Observability Platform

A **framework-agnostic** agent control plane on top of [Langfuse](https://langfuse.com).  
Connect any agent or tool — PydanticAI, LangChain, raw OpenAI, or anything else — and get full observability, automated evaluation, prompt versioning, and dataset experiments out of the box.

## Services

| Service | URL | Purpose |
|---|---|---|
| **Langfuse UI** | http://localhost:3000 | Traces, prompts, datasets, annotation queues |
| **Control Plane API** | http://localhost:8500 | Agent registry, run tracking, eval dispatch |
| **Dashboard** | http://localhost:8501 | Platform KPIs, score trends, alerts, experiments |

## Architecture

```
Your Agent Code
     │
     ▼
sdk/adapters/           ← thin connector per framework
  pydantic_ai.py        ← Agent.instrument_all() → OTEL → Langfuse
  langchain.py          ← Langfuse callback handler
  openai.py             ← Langfuse OpenAI wrapper
  @agent_run decorator  ← for any other callable
     │
     ├──── OTEL spans ──────────────► Langfuse :3000
     │                                (traces, scores, prompts, datasets)
     └──── POST /runs ─────────────► Control Plane :8500
                                      (registry, run tracker, eval dispatch)
                                           │
                                      eval pipeline
                                      llm_judge + rule_based
                                           │
                                      POST scores ──► Langfuse :3000
```

## Quick Start

### 1. Prerequisites

- Langfuse running (already up at http://localhost:3000)
- Python 3.11+

### 2. Install

```bash
cd agent_platform
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env:
#   LANGFUSE_PUBLIC_KEY  — from Langfuse UI → Settings → API Keys
#   LANGFUSE_SECRET_KEY  — same
#   OPENAI_API_KEY       — your OpenAI key
```

### 4. Start the platform

```bash
# Terminal 1 — Control Plane API
uvicorn control_plane.main:app --reload --port 8500

# Terminal 2 — Dashboard
streamlit run dashboard/app.py

# Or with Docker Compose
docker compose up
```

### 5. Seed data (optional)

```bash
python scripts/seed_prompts.py   # push versioned prompts to Langfuse
python scripts/seed_dataset.py   # create benchmark Q&A dataset
```

### 6. Run an example

```bash
python examples/pydantic_ai_example.py
python examples/langchain_example.py
python examples/openai_example.py
```

### 7. Run a dataset experiment

```bash
python scripts/run_experiment.py \
    --dataset platform/qa-benchmark \
    --experiment-name my-first-run
```

## Connecting Your Own Agent (from a different project)

Your agent lives in its own project/repo. There are two ways to connect it to this platform:

---

### Option A — Install the SDK package (recommended)

The `sdk/` directory is a pip-installable package. Install it once into your agent project's environment:

```bash
# From inside your agent project's virtual environment:
pip install -e /path/to/agent_platform[pydantic-ai]
# or for LangChain:
pip install -e /path/to/agent_platform[langchain]
# or everything:
pip install -e /path/to/agent_platform[all]
```

After that, import normally in your agent project:

#### PydanticAI

```python
# your_agent_project/my_agent.py
import asyncio
from pydantic_ai import Agent
from sdk.adapters.pydantic_ai import PydanticAIAdapter

agent = Agent("openai:gpt-4o", system_prompt="You are helpful.", instrument=True)

adapter = PydanticAIAdapter(
    agent=agent,
    name="my-agent",
    description="My custom agent",
    evaluators=["llm_judge", "rule_based"],
    control_plane_url="http://localhost:8500",  # platform address
)

result = await adapter.run("Your prompt here")
```

#### LangChain

```python
from sdk.adapters.langchain import LangChainAdapter

adapter = LangChainAdapter(
    chain=my_chain,
    name="my-chain",
    evaluators=["llm_judge"],
    control_plane_url="http://localhost:8500",
)
result = adapter.invoke({"input": "Your input here"})
```

#### Raw OpenAI

```python
from sdk.adapters.openai import OpenAIAdapter

adapter = OpenAIAdapter(
    name="my-openai-agent",
    evaluators=["rule_based"],
    control_plane_url="http://localhost:8500",
)
response = adapter.chat(messages=[{"role": "user", "content": "Hello"}])
```

#### Any callable (decorator)

```python
from sdk.connector import agent_run

@agent_run(name="my-tool", evaluators=["rule_based"], control_plane_url="http://localhost:8500")
def my_tool(query: str) -> str:
    return call_some_llm(query)
```

---

### Option B — Pure HTTP (no SDK install needed)

If you don't want to install anything, just POST directly to the control plane REST API using `httpx` or `requests`. No import from this project is required.

```python
# your_agent_project/my_agent.py
import httpx, time, uuid

CONTROL_PLANE = "http://localhost:8500"

# 1. Register your agent once (on startup)
httpx.post(f"{CONTROL_PLANE}/agents/register", json={
    "name": "my-agent",
    "description": "My remote agent",
    "framework": "generic",
    "evaluators": ["llm_judge", "rule_based"],
})

# 2. After each run, report it (trace_id comes from your own Langfuse setup)
httpx.post(f"{CONTROL_PLANE}/runs", json={
    "agent_name": "my-agent",
    "trace_id": "<langfuse-trace-id>",
    "input": "user prompt here",
    "output": "agent response here",
    "status": "completed",
    "latency_ms": 420.0,
})

# 3. Optionally trigger evals manually on any trace
httpx.post(f"{CONTROL_PLANE}/evals/run", json={
    "trace_id": "<langfuse-trace-id>",
    "input": "user prompt here",
    "output": "agent response here",
    "evaluators": ["llm_judge", "rule_based"],
})
```

The full API reference is at **http://localhost:8500/docs** (Swagger UI).

---

### How tracing works with PydanticAI (OTEL)

PydanticAI sends traces directly to Langfuse via OpenTelemetry — no extra code needed beyond setting two env vars in your agent project:

```bash
# In your agent project's .env
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:3000/api/public/otel
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <base64(pk-lf-...:sk-lf-...)>
```

Or in code (before creating any Agent):

```python
import os, base64

pk = "pk-lf-..."
sk = "sk-lf-..."
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:3000/api/public/otel"
os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = (
    "Authorization=Basic " + base64.b64encode(f"{pk}:{sk}".encode()).decode()
)

from pydantic_ai import Agent
Agent.instrument_all()   # all agents in this process are now traced
```

The `PydanticAIAdapter` does this automatically when you use Option A.

## Project Structure

```
agent_platform/
├── sdk/                    # Connector SDK — import into any agent project
│   ├── schemas.py          # AgentRegistration, AgentRunReport, Score models
│   ├── connector.py        # BaseConnector + @agent_run decorator
│   └── adapters/
│       ├── pydantic_ai.py  # PydanticAI adapter
│       ├── langchain.py    # LangChain adapter
│       └── openai.py       # Raw OpenAI adapter
├── platform/               # FastAPI control plane
│   ├── main.py             # App entrypoint
│   ├── config.py           # Settings
│   ├── langfuse_client.py  # Langfuse SDK helpers
│   ├── registry.py         # Agent registry
│   ├── runner.py           # Run tracker + eval dispatch
│   ├── evals/
│   │   ├── llm_judge.py    # LLM-as-judge (quality, relevance)
│   │   └── rule_based.py   # Deterministic rule checks
│   └── routers/
│       ├── agents.py       # GET/POST /agents
│       ├── runs.py         # POST /runs, GET /runs
│       ├── evals.py        # POST /evals/run
│       └── datasets.py     # CRUD /datasets
├── dashboard/              # Streamlit dashboard
│   ├── app.py              # Home + shared helpers
│   └── pages/
│       ├── 1_overview.py   # KPI cards, run charts
│       ├── 2_eval_trends.py# Score trends over time
│       ├── 3_live_runs.py  # Auto-refresh run status
│       ├── 4_alerts.py     # Threshold alerts
│       ├── 5_experiments.py# Dataset experiment comparison
│       └── 6_agents.py     # Agent registry view
├── examples/               # Runnable examples
├── scripts/                # Seed + experiment scripts
├── .env.example
├── requirements.txt
└── docker-compose.yml
```

## Evaluators

| Name | Type | Scores produced |
|---|---|---|
| `llm_judge` | LLM-as-judge (GPT-4o-mini) | `llm_judge.quality`, `llm_judge.relevance` |
| `rule_based` | Deterministic | `rule.not_empty`, `rule.length_ok`, `rule.no_error_msg`, `rule.json_valid` |

All scores are pushed to Langfuse and visible inline on each trace.

## Adding a New Evaluator

```python
# platform/evals/my_eval.py
from platform.evals.base import AbstractEvaluator
from sdk.schemas import Score

class MyEvaluator(AbstractEvaluator):
    @property
    def name(self) -> str:
        return "my_eval"

    async def evaluate(self, trace_id, output, input="") -> list[Score]:
        # your logic here
        return [Score(name="my_eval.score", value=0.9, trace_id=trace_id)]
```

Then register it in `platform/routers/evals.py`:
```python
EVALUATOR_MAP["my_eval"] = MyEvaluator()
```
