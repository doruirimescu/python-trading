PY=.venv/bin/python
.PHONY: env test test-all lint run check
env:
	/home/doru/.local/bin/uv venv --python 3.13 .venv
	/home/doru/.local/bin/uv pip install --python $(PY) -e ".[dev]"
test:
	.venv/bin/pytest -q
test-all:
	.venv/bin/pytest -q -m "not network"
perf:
	.venv/bin/pytest -q -m perf -s
lint:
	.venv/bin/ruff check src tests strategies
run:
	$(PY) -m tradelab run experiments/example_daily.yaml
check:
	$(PY) -m tradelab check-causality experiments/example_daily.yaml
