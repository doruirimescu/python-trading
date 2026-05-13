import io
import contextlib
import os

from Trading.macro.liquidity_monitor import LiquidityMonitor
from Trading.utils.send_email import send_email


def run() -> None:
    api_key = os.environ["FRED_API_KEY"]
    monitor = LiquidityMonitor(api_key=api_key)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        monitor.run_analysis()
    report = buf.getvalue()

    # Score is still accessible after run_analysis() populated self.*
    total_score, _ = monitor.calculate_score()

    if total_score < 30:
        status = "GREEN"
    elif total_score < 60:
        status = "YELLOW"
    elif total_score < 80:
        status = "ORANGE"
    else:
        status = "RED"

    subject = f"[Monthly Macro] Market Crash Probability: {total_score:.1f}% — {status}"
    print(report)
    send_email(subject=subject, body=report)
    print("Email sent.")


if __name__ == "__main__":
    run()
