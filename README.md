# GridWise Energy Optimizer

A FastAPI service for the BUP CSE Fest 2026 GridWise preliminary. It combines language-model directive interpretation, deterministic guardrails, exact linear optimization, and independent schedule replay.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Check readiness:

```bash
curl http://localhost:8000/health
```

The interpreter uses a local development fallback when `MODEL_API_KEY` and `MODEL_API_URL` are not configured. For judging, configure an OpenAI-compatible model endpoint:

```bash
export MODEL_API_URL=https://api.openai.com/v1/chat/completions
export MODEL_API_KEY=your-key
export MODEL_NAME=gpt-4o-mini
```

No secret values belong in this repository.

## Public sample test

Run all ten public cases:

```bash
pytest -q
```

The tests independently replay every returned schedule and verify the energy, battery, and directive constraints. A sample request can be sent by extracting any `.cases[].input` object from the supplied JSON file.

For the complete endpoint testing workflow, Swagger instructions, negative cases, hidden-style paraphrase data, and performance checklist, see [test_guidline.md](test_guidline.md).

## Docker

```bash
docker build -t gridwise:local .
docker run --rm -p 8000:8000 --env-file .env gridwise:local
```

## Design

The LLM only maps natural language to a typed directive intermediate representation. Guardrails reject malformed or unsupported output. SciPy HiGHS minimizes grid cost subject to the directive constraints. A separate replay validator proves the final plan before the response is returned. See [plan.md](plan.md) and [docs/architecture.md](docs/architecture.md).
