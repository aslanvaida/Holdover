PYTHON ?= python

.PHONY: requirements demo backtest test

requirements:
	$(PYTHON) -m pip install -r requirements.txt

demo:
	$(PYTHON) scripts/run_demo.py

backtest:
	$(PYTHON) scripts/backtest.py

test:
	$(PYTHON) -m pytest -q
