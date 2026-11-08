PY=.venv/bin/python
.PHONY: env test lint smoke sp500
env:
	/home/doru/.local/bin/uv venv --python 3.13 .venv
	/home/doru/.local/bin/uv pip install --python $(PY) -e ".[dev]"
test:
	.venv/bin/pytest -q
lint:
	.venv/bin/ruff check src tests
smoke:
	$(PY) -m perfectshape scan configs/smoke.yaml
sp500:
	$(PY) -m perfectshape scan configs/sp500.yaml
