"""
ChemAgent CLI: interactive terminal interface.

Usage:
    python -m src.interface.cli
    python -m src.interface.cli "What was the minimum DO in the first 24 hours?"
    python -m src.interface.cli --no-stream "..."  # disable step-by-step output
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from smolagents.agents import ActionStep, FinalAnswerStep


def _run_streaming(agent, question: str) -> str:
    """Run agent with step-by-step output and return final answer."""
    step_num = 0
    for event in agent.run(question, stream=True):
        if isinstance(event, ActionStep):
            step_num += 1
            if event.tool_calls:
                tc = event.tool_calls[0]
                args_str = ", ".join(
                    f"{k}={v!r}" for k, v in (tc.arguments or {}).items()
                )
                print(f"  Step {step_num}: {tc.name}({args_str})")
            if event.error:
                print(f"  [error] {event.error}")
        elif isinstance(event, FinalAnswerStep):
            return str(event.output)
    return "[no final answer]"


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="ChemAgent CLI")
    ap.add_argument("question", nargs="?", help="Question to ask (omit for interactive loop)")
    ap.add_argument("--no-stream", action="store_true", help="Disable step-by-step output")
    args = ap.parse_args()

    from src.agent.chem_agent import build_agent
    print("Loading ChemAgent...", flush=True)
    agent = build_agent()
    print("Ready. Type 'exit' or Ctrl-C to quit.\n")

    def ask(q: str) -> None:
        print(f"\nQ: {q}")
        if args.no_stream:
            answer = str(agent.run(q))
        else:
            answer = _run_streaming(agent, q)
        print(f"\nA: {answer}\n")
        print("-" * 60)

    if args.question:
        ask(args.question)
        return

    # Interactive loop
    while True:
        try:
            q = input("Ask> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye.")
            break
        if not q or q.lower() in {"exit", "quit", "q"}:
            print("Bye.")
            break
        try:
            ask(q)
        except Exception as e:
            print(f"[error] {e}")


if __name__ == "__main__":
    main()
