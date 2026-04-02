# Run from project root. Uses .venv if present (no need to activate manually).
PYTHON ?= .venv/bin/python
UVICORN ?= $(PYTHON) -m uvicorn

.PHONY: dev install ui-build

dev:
	$(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

install:
	$(PYTHON) -m pip install -r requirements.txt

ui-build:
	cd frontend && npm install && npm run build
