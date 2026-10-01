# Handy shortcuts (macOS / Linux). Run `make help` to list them.
PY ?= python3
VENV = backend/.venv
BIN = $(VENV)/bin

.PHONY: help setup backend frontend test build sample demo docker clean

help:
	@echo "make setup     - one-time: create Python venv, install backend + frontend deps, create .env"
	@echo "make backend   - start the API on http://localhost:8000 (terminal 1)"
	@echo "make frontend  - start the React dev server on http://localhost:5173 (terminal 2)"
	@echo "make demo      - run everything WITHOUT an AI key (mock mode) on http://localhost:8000"
	@echo "make test      - run the backend test suite"
	@echo "make build     - build the production frontend into frontend/dist"
	@echo "make sample    - regenerate samples/sample_paper.pdf"
	@echo "make docker    - run Postgres + app with Docker Compose"

setup:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r backend/requirements-dev.txt
	cd frontend && npm install
	@test -f .env || (cp .env.example .env && echo "Created .env - add your GROQ_API_KEY to it")

backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

demo: build
	cd backend && AI_PROVIDER=mock .venv/bin/uvicorn app.main:app --port 8000

test:
	$(BIN)/pytest

build:
	cd frontend && npm run build

sample:
	$(BIN)/python scripts/make_sample_pdf.py

docker:
	docker compose up --build

clean:
	rm -rf backend/data frontend/dist lambda/build lambda/lambda_function.zip .pytest_cache
