PYTHON ?= python

.PHONY: install run test render-sample

install:
	$(PYTHON) -m pip install -e .[dev]

run:
	$(PYTHON) -m streamlit run streamlit_app.py

test:
	$(PYTHON) -m pytest

render-sample:
	$(PYTHON) -m src.services.rendering.text_renderer

