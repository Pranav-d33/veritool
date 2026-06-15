.PHONY: test verify benchmark compare all clean install

PYTHON = python3
PYTEST = PYTHONPATH="." $(PYTHON) -m pytest

test:
	$(PYTEST) tests/ -v --tb=short

verify:
	lean Lean/Trace.lean

benchmark:
	$(PYTHON) -m benchmark.report

all: verify test benchmark compare

compare:
	PYTHONPATH="." $(PYTHON) -m benchmark.compare

install:
	pip install -e ".[dev]"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	find Lean -type f -name '*.olean' -delete
