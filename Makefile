PYTHON ?= python

.PHONY: install run run-legacy test render-sample

install:
	$(PYTHON) -m pip install -e .[dev]

run:
	$(PYTHON) -m uvicorn backend.main:app --reload

run-legacy:
	$(PYTHON) -m streamlit run backend/legacy/streamlit_app.py

test:
	$(PYTHON) -m pytest

render-sample:
	$(PYTHON) -m backend.engine.services.rendering.text_renderer

