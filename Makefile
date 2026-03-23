.PHONY: install dev channels test lint format run serve clean \
        docker-build docker-chat docker-serve docker-down docker-logs

PYTHON := .venv/Scripts/python.exe
UV     := uv

# ── Setup ────────────────────────────────────────────────────────────────────
install:
	$(UV) venv
	$(UV) pip install -e .

dev: install
	$(UV) pip install -e ".[dev]"

channels: install
	$(UV) pip install -e ".[channels]"

all-deps: install
	$(UV) pip install -e ".[channels,dev]"

# ── Testing ──────────────────────────────────────────────────────────────────
test:
	$(PYTHON) -m pytest tests/ -v --tb=short

test-smoke:
	$(PYTHON) -m pytest tests/test_interactive_smoke.py -v --tb=short

test-cov:
	$(PYTHON) -m pytest tests/ --cov=claw --cov-report=html --cov-report=term-missing

# ── Linting ──────────────────────────────────────────────────────────────────
lint:
	$(PYTHON) -m ruff check claw/ tests/

format:
	$(PYTHON) -m ruff format claw/ tests/
	$(PYTHON) -m ruff check --fix claw/ tests/

# ── Run (local) ──────────────────────────────────────────────────────────────
chat:
	$(PYTHON) -m claw.cli chat --workspace ./workspace

onboard:
	$(PYTHON) -m claw.cli onboard --workspace ./workspace

status:
	$(PYTHON) -m claw.cli status

serve:
	$(PYTHON) -m claw.cli serve --workspace ./workspace

# ── Docker ───────────────────────────────────────────────────────────────────
docker-build:
	docker compose build

docker-chat:
	docker compose --profile chat up claw

docker-serve:
	docker compose --profile serve up -d claw-serve

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

# ── Clean ────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .ruff_cache .mypy_cache .pytest_cache htmlcov
	rm -rf dist build *.egg-info
