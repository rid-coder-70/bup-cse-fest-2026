# GridWise Energy Optimizer

A FastAPI-based solution for the BUP CSE Fest 2026 GridWise challenge. The service reads operator notes, interprets them into structured directives, validates them with guardrails, solves the 24-hour optimization exactly, and returns a schedule that is independently replay-checked before responding.

## Why this solution is strong

- Deterministic guardrails protect against invalid or unsupported model output.
- The optimization is solved with SciPy HiGHS for exact, fast scheduling.
- An independent replay validator proves feasibility before returning the final response.
- Local fallback behavior keeps development and public sample testing working even without a model key.
- The service is container-ready and easy to deploy on free hosting platforms.

## Project structure

- `app/` — FastAPI app, request models, interpreter, optimizer, guardrails, and replay validator
- `tests/` — unit and hidden-style validation checks
- `scripts/test_public_api.py` — HTTP validation against the public JSON sample cases
- `docs/` — architecture and testing documentation
- `plan.md` — implementation plan
- `Dockerfile` — container build definition

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Check app health:

```bash
curl http://localhost:8000/health
```

## Optional model configuration

If you want the interpreter to call a hosted OpenAI-compatible model, set the environment variables before starting the API:

```bash
export MODEL_API_URL=https://api.openai.com/v1/chat/completions
export MODEL_API_KEY=your-key
export MODEL_NAME=gpt-4o-mini
```

If these are not set, the app falls back to a local deterministic interpretation path for development and public-case validation.

## Testing

Run the full automated checks:

```bash
pytest -q
```

Test the public HTTP cases directly:

```bash
python scripts/test_public_api.py http://127.0.0.1:8000
```

For a complete API testing guide, including curl examples, Swagger flow, hidden cases, and challenge-specific validation workflows, see [test_guidline.md](test_guidline.md).

## Docker

Build and run the container:

```bash
docker build -t gridwise:local .
docker run --rm -p 8000:8000 --env-file .env gridwise:local
```

## Deployment notes

This project is ready for simple cloud deployment on platforms such as Render, Railway, or a lightweight VPS with Docker. The app does not require a database and is designed to run as a single FastAPI service.

## Architecture references

- [docs/architecture.md](docs/architecture.md)
- [plan.md](plan.md)
- [test_guidline.md](test_guidline.md)

> No secrets or API credentials should be committed to the repository. Use `.env` locally and keep a safe `.env.example` template only.
