from __future__ import annotations

from pathlib import Path

from model.config_loader import ConfigError, load_config
from composition_root import build_app


CONFIG_FILENAME = "config.yaml"


def load_runtime_config() -> object:
    config_path = Path(__file__).with_name(CONFIG_FILENAME)
    return load_config(config_path)


def main() -> int:
    try:
        runtime_config = load_runtime_config()
    except ConfigError as exc:
        print(f"Failed to load {CONFIG_FILENAME}: {exc}")
        return 1

    print(f"Loaded {CONFIG_FILENAME} (version {runtime_config.raw.config_version})")

    app = build_app(runtime_config.raw)
    print("Application successfully composed with the following components:")
    print(f"- Mean Estimator: {type(app.mean_estimator).__name__}")
    print(f"- Volatility Estimator: {type(app.volatility_estimator).__name__}")
    print(f"- Deviation Detector: {type(app.deviation_detector).__name__}")
    print(f"- Reversion Criteria: {type(app.reversion_criteria).__name__}")
    print(f"- Failure Criteria: {type(app.failure_criteria).__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
