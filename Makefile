.PHONY: help install run-api run-dashboard run-mcp demo test lint format clean check-all

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies via uv
	uv sync --all-extras

run-api:  ## Start FastAPI on :8000 with auto-reload
	uv run uvicorn finops.api.main:app --host 0.0.0.0 --port 8000 --reload

run-dashboard:  ## Start Streamlit dashboard on :8501
	uv run streamlit run src/finops/dashboard/app.py --server.port 8501

run-mcp:  ## Start MCP server (stdio transport)
	uv run python -m finops.mcp_server.server

run-mcp-http:  ## Start MCP server (HTTP transport on :8765 for inspection)
	uv run python -m finops.mcp_server.server --http

demo:  ## End-to-end demo: ingest → scan → analyze → report
	uv run finops demo

ingest:  ## Ingest a sample billing file (override with FILE=path)
	uv run finops ingest $(or $(FILE),samples/aws_cur_sample.csv)

scan:  ## Run detection engine on current data
	uv run finops scan

analyze:  ## Run sub-agent orchestrator (Analyzer + Remediator)
	uv run finops analyze

reset:  ## Wipe local SQLite database
	rm -f data/finops.db && uv run finops init-db

test:  ## Run pytest suite
	uv run pytest -v

test-fast:  ## Run pytest excluding integration tests
	uv run pytest -v -m "not integration and not llm"

lint:  ## Lint with ruff
	uv run ruff check src tests

format:  ## Format with ruff
	uv run ruff format src tests

typecheck:  ## Type-check with mypy
	uv run mypy src/finops

check-all: lint typecheck test  ## Run lint + typecheck + tests

clean:  ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache .uv-cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +

# Vibe Coding meta targets
elapsed:  ## Show elapsed time since session start
	@uv run python -c "import json,datetime as d; m=json.load(open('.session_meta.json')); s=d.datetime.fromisoformat(m['session_started_at_utc'].replace('Z','+00:00')); now=d.datetime.now(d.timezone.utc); el=now-s; print(f'Elapsed: {int(el.total_seconds()//3600)}h {int(el.total_seconds()%3600//60)}m {int(el.total_seconds()%60)}s')"

audit:  ## Print latest entries from prompts.md
	@tail -60 prompts.md
