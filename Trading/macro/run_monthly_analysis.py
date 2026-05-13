import io
import contextlib
import os
import sys

from Trading.config.config import MACRO_GENERATED_PATH
from Trading.macro.liquidity_monitor import LiquidityStressMonitor
from Trading.utils.send_email import send_email


def run() -> None:
    api_key = os.environ["FRED_API_KEY"]
    monitor = LiquidityStressMonitor(api_key=api_key)

    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            monitor.run_analysis()
    except Exception:
        # Flush whatever was captured before the crash so CI logs show it
        print(buf.getvalue(), file=sys.stderr)
        raise
    report = buf.getvalue()

    total_score = monitor.liquidity_stress_score

    if total_score < 25:
        status = "GREEN"
    elif total_score < 45:
        status = "YELLOW"
    elif total_score < 65:
        status = "ORANGE"
    elif total_score < 80:
        status = "RED"
    else:
        status = "CRITICAL"

    subject = f"[Monthly Macro] Market Crash Probability: {total_score:.1f}% — {status}"
    monitor.save_results(MACRO_GENERATED_PATH)
    print(report)
    send_email(subject=subject, body=report)
    print("Email sent.")


if __name__ == "__main__":
    run()
