.PHONY: test verify demo clean install cli dashboard

PYTHON = python3
PYTEST = PYTHONPATH="." $(PYTHON) -m pytest

test:
	$(PYTEST) tests/ -v --tb=short

test-all:
	$(PYTEST) tests/ -v

verify:
	lean Lean/Policy.lean
	lean Lean/Verify.lean
	$(PYTHON) -c "import subprocess; r = subprocess.run(['lean', 'Lean/Invalid.lean'], capture_output=True); assert r.returncode != 0, 'Invalid.lean should fail'; print('Invalid.lean correctly rejected')"

demo:
	PYTHONPATH="." $(PYTHON) demo_tahoe.py
	PYTHONPATH="." $(PYTHON) demo_deletion.py

llm-demo:
	$(PYTHON) demo.py

cli:
	PYTHONPATH="." $(PYTHON) -m cli --help

dashboard:
	streamlit run dashboard/app.py --server.port=8501

install:
	pip install -e ".[dev]"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	find Lean -type f -name '*.olean' -delete

.PHONY: test-fast
test-fast:
	$(PYTEST) tests/ -x -q --tb=short
