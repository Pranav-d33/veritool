.PHONY: test verify demo clean

PYTHON = python3
PYTEST = PYTHONPATH="." $(PYTHON) -m pytest

test:
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

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	find Lean -type f -name '*.olean' -delete
