.PHONY: test verify benchmark compare taubench ablation graphs all install clean install-cvc5

PYTHON = python3
PYTEST = PYTHONPATH="." $(PYTHON) -m pytest
TAUBENCH_PATH = /tmp/tau2-bench/data/tau2/domains
ABLATION_PYTHON = PYTHONPATH=".:$(TAUBENCH_PATH)/.." $(PYTHON)

# ── Core ───────────────────────────────────────────────────────────────────

test:
	$(PYTEST) tests/ -v --tb=short

verify:
	lean Lean/Trace.lean

benchmark:
	$(PYTHON) -m benchmark.report

compare:
	PYTHONPATH="." $(PYTHON) -m benchmark.compare

# ── TAU-bench ──────────────────────────────────────────────────────────────

taubench:
	PYTHONPATH=".:$(TAUBENCH_PATH)/.." $(PYTHON) benchmark/taubench_benchmark.py

# ── Ablation experiments ───────────────────────────────────────────────────

ablation:
	PYTHONPATH=".:$(TAUBENCH_PATH)/.." $(PYTHON) benchmark/ablation_benchmark.py

# Ablation 2 (solver swap) requires CVC5 and the cvc5 venv:
ablation-cvc5:
	PYTHONPATH=".:$(TAUBENCH_PATH)/.." /tmp/cvc5_venv/bin/python3 benchmark/ablation_benchmark.py

# ── Graphs ─────────────────────────────────────────────────────────────────

graphs:
	$(PYTHON) benchmark/graphs/generate_graphs.py

# ── Full pipeline ──────────────────────────────────────────────────────────

all: verify test benchmark compare taubench ablation-cvc5 graphs
	@echo "Full pipeline complete."

# ── Setup ──────────────────────────────────────────────────────────────────

install:
	pip install -e ".[dev]"

install-cvc5:
	python3 -m venv /tmp/cvc5_venv
	/tmp/cvc5_venv/bin/pip install cvc5 z3-solver

# ── Cleanup ────────────────────────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	find Lean -type f -name '*.olean' -delete

# ── TAU-bench data ─────────────────────────────────────────────────────────

TAU_REPO = /tmp/tau2-bench

$(TAU_REPO):
	git clone --depth=1 https://github.com/sierra-research/tau-bench.git $(TAU_REPO)
