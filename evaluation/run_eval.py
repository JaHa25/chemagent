"""
Headless evaluation runner.

Usage (from chemagent/):
    python evaluation/run_eval.py                              # all 8 queries, default model
    python evaluation/run_eval.py --quick                      # Q1+Q2 only (smoke)
    python evaluation/run_eval.py --query Q3                   # single query
    python evaluation/run_eval.py --profile local_gemma_e2b    # single alternate model
    python evaluation/run_eval.py --judge claude_haiku         # LLM-as-judge scoring
    python evaluation/run_eval.py --models claude_haiku,local_gemma_e2b --judge claude_haiku
"""

from __future__ import annotations

import argparse
import contextlib
import io
import re
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent.chem_agent import build_agent

_NULL = io.StringIO()

# ---------------------------------------------------------------------------
# Eval query set
# ---------------------------------------------------------------------------
EVAL_QUERIES = [
    {
        "id": "Q1", "type": "Descriptive",
        "question": "What was the average pH over the last 12 hours?",
        "expected": "Measured pH mean ~6.99 [6.95-7.05]; MUST flag sensor drift contamination.",
        "checks": [
            (r"6\.9\d|7\.0\d", "pH value in expected range"),
            (r"drift|sensor|unreliable|fault", "flags sensor drift caveat"),
        ],
    },
    {
        "id": "Q2", "type": "Descriptive",
        "question": "What was the maximum biomass concentration between 20 h and 36 h?",
        "expected": "~15.0 g/L (acceptable 14.5-15.5).",
        "checks": [(r"1[45]\.\d", "biomass max ~15 g/L")],
    },
    {
        "id": "Q3", "type": "Descriptive",
        "question": "What was the minimum dissolved oxygen in the first 24 hours?",
        "expected": "~59.8 % (acceptable 58-62 %). Should NOT mention the later O2 limitation.",
        "checks": [(r"5[89]\.\d|6[012]\.\d", "DO min ~60%")],
    },
    {
        "id": "Q4", "type": "Diagnostic",
        "question": "Were there any temperature anomalies after 24 h?",
        "expected": "No large anomalies; minor +0.4 degC transient during O2 limitation [38-42 h].",
        "checks": [(r"no|minor|small|transient|0\.4|38|42", "notes minor/no anomaly")],
    },
    {
        "id": "Q5", "type": "Diagnostic",
        "question": "Did dissolved oxygen show an unusual drop near 38 h?",
        "expected": "Yes: drop from ~65% to ~33.7%, dip of ~31 pp during [38,42) h.",
        "checks": [
            (r"yes|drop|dip|decrease", "confirms drop"),
            (r"3[0-9]|65|limitation", "references magnitude or event"),
        ],
    },
    {
        "id": "Q6", "type": "Diagnostic",
        "question": "Was there evidence of pH drift after 42 h?",
        "expected": "Yes: upward drift ~0.008 pH/h; MUST be flagged as sensor fault.",
        "checks": [
            (r"yes|drift|upward|increas", "confirms drift"),
            (r"sensor|fault|artifact|not.*process", "attributes to sensor"),
        ],
    },
    {
        "id": "Q7", "type": "Comparative",
        "question": "How did product titer change before and after the feed adjustment?",
        "expected": "Pre-slope ~0.19, post-slope ~0.35 g/L/h; ratio ~1.8x (accept 1.5-2.2x).",
        "checks": [(r"1\.\d|2\.\d|0\.[12]\d|0\.3\d", "reports numeric slopes or ratio")],
    },
    {
        "id": "Q8", "type": "Comparative",
        "question": "How did substrate concentration change after the oxygen limitation event?",
        "expected": "Decrease ~1.8 g/L (~23%); pre-mean ~7.59, post-mean ~5.83 g/L.",
        "checks": [(r"1\.[5-9]|2\.[0-2]|decreas|drop|lower", "reports decrease ~1.8 g/L")],
    },
]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_answer(answer: str, checks) -> tuple[int, int, list[str]]:
    notes, passed = [], 0
    for pattern, hint in checks:
        if re.search(pattern, answer, flags=re.IGNORECASE):
            passed += 1
            notes.append(f"  [OK]   {hint}")
        else:
            notes.append(f"  [MISS] {hint}")
    return passed, len(checks), notes


def judge_answer(
    question: str,
    expected: str,
    agent_answer: str,
    judge_profile: str | None,
) -> tuple[str, str]:
    """Call a second LLM to rate the answer as correct/partial/incorrect."""
    if not judge_profile:
        return "unscored", "No judge model configured."

    JUDGE_PROMPT = f"""You are evaluating an AI agent answer against a ground-truth expected answer.

Question: {question}

Expected answer (ground truth):
{expected}

AI agent answer:
{agent_answer}

Rate the agent answer strictly as one of:
- correct   (numerically and qualitatively within stated tolerances, important caveats present)
- partial   (direction correct but magnitude wrong, OR a key caveat missing)
- incorrect (wrong answer, hallucinated, or tool error)

Reply with exactly two lines:
Verdict: <correct|partial|incorrect>
Justification: <one sentence>"""

    try:
        from src.model_registry import ModelRegistry
        from smolagents import LiteLLMModel

        registry = ModelRegistry()
        profile = registry.get(judge_profile)
        kwargs: dict = {"model_id": profile.model_id, "api_key": profile.api_key}
        if profile.api_base:
            kwargs["api_base"] = profile.api_base

        judge_model = LiteLLMModel(**kwargs)
        messages = [{"role": "user", "content": JUDGE_PROMPT}]
        raw = judge_model.generate(messages)
        text = raw.content if hasattr(raw, "content") else str(raw)

        verdict, justification = "unscored", text.strip()
        for line in text.splitlines():
            ll = line.lower()
            if ll.startswith("verdict:"):
                verdict = line.split(":", 1)[1].strip().lower()
            elif ll.startswith("justification:"):
                justification = line.split(":", 1)[1].strip()
        return verdict, justification

    except Exception as e:
        return "unscored", f"Judge error: {e}"


# ---------------------------------------------------------------------------
# Single-model run
# ---------------------------------------------------------------------------

def run(
    queries: list[dict],
    out_path: Path,
    model_profile: str | None = None,
    judge_profile: str | None = None,
) -> tuple[int, list[dict]]:
    """Run queries against one agent. Returns (exit_code, per_query_results)."""
    agent = build_agent(model_profile)
    total_p = total_t = 0
    results: list[dict] = []
    md = [f"# ChemAgent: Evaluation Results\n"]
    profile_label = model_profile or "default"
    md.append(f"Model profile: `{profile_label}` | {len(queries)} queries\n")

    for q in queries:
        print(f"\n=== {q['id']} ({q['type']}): {q['question']}")
        t0 = time.time()
        tool_failures = 0
        try:
            with contextlib.redirect_stdout(_NULL), contextlib.redirect_stderr(_NULL):
                answer = str(agent.run(q["question"]))
            err = None
        except Exception as e:
            answer = f"[Agent error] {e}"
            err = e
            tool_failures += 1
        dt = time.time() - t0

        p, t, notes = score_answer(answer, q["checks"])
        verdict, justification = judge_answer(q["question"], q["expected"], answer, judge_profile)
        total_p += p
        total_t += t
        status = "PASS" if p == t else ("PARTIAL" if p > 0 else "FAIL")

        print(f"    -> {status} ({p}/{t}, {dt:.1f}s)  judge={verdict}")
        for n in notes:
            print(n)

        results.append({
            "id": q["id"], "type": q["type"], "question": q["question"],
            "status": status, "passed": p, "total": t,
            "latency_s": round(dt, 1), "verdict": verdict,
            "justification": justification, "tool_failures": tool_failures,
            "answer": answer,
        })

        md.append(f"## {q['id']} ({q['type']}): {status} ({p}/{t}) | judge: {verdict}")
        md.append(f"**Q:** {q['question']}  ")
        md.append(f"**Expected:** {q['expected']}  ")
        md.append(f"**Runtime:** {dt:.1f}s\n")
        md.append("**Agent answer:**\n```")
        md.append(answer)
        md.append("```")
        md.append(f"**Judge:** {verdict}: {justification}")
        md.append("**Checks:**")
        md.extend(notes)
        md.append("\n---\n")
        if err:
            md.append(f"Exception: `{err}`\n")

    summary = f"\n## Overall: {total_p}/{total_t} regex checks passed"
    md.insert(2, summary + "\n")
    print(summary)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(md), encoding="utf-8")
    print(f"Report written to {out_path}")
    return (0 if total_p == total_t else 1), results


# ---------------------------------------------------------------------------
# Multi-model benchmark
# ---------------------------------------------------------------------------

def run_benchmark(
    queries: list[dict],
    model_names: list[str],
    judge_profile: str | None,
    out_path: Path,
) -> int:
    all_results: dict[str, list[dict]] = {}

    for model_name in model_names:
        print(f"\n{'='*60}\n  Model: {model_name}\n{'='*60}")
        individual_out = out_path.parent / f"results_{model_name}.md"
        _, results = run(queries, individual_out, model_profile=model_name, judge_profile=judge_profile)
        all_results[model_name] = results

    query_ids = [q["id"] for q in queries]
    header = ["Model"] + query_ids + ["Accuracy%", "Avg latency(s)", "Tool failures"]

    rows = []
    for model_name, results in all_results.items():
        correct = sum(1 for r in results if r["verdict"] == "correct")
        partial = sum(1 for r in results if r["verdict"] == "partial")
        # correct=1.0, partial=0.5, incorrect=0.0, unscored uses regex status
        scored = [r for r in results if r["verdict"] not in ("unscored",)]
        if scored:
            accuracy = (correct + 0.5 * partial) / len(results) * 100
        else:
            accuracy = sum(r["passed"] for r in results) / max(sum(r["total"] for r in results), 1) * 100
        avg_lat = sum(r["latency_s"] for r in results) / len(results) if results else 0.0
        tool_fail = sum(r["tool_failures"] for r in results)

        cells = []
        for r in results:
            v = r["verdict"]
            cell = {"correct": "PASS", "partial": "PART", "incorrect": "FAIL"}.get(v, r["status"])
            cells.append(cell)

        rows.append([model_name] + cells + [f"{accuracy:.0f}%", f"{avg_lat:.1f}s", str(tool_fail)])

    md = ["# ChemAgent: Benchmark Comparison\n",
          f"Models: {', '.join(model_names)} | Judge: {judge_profile or 'regex only'}\n",
          "| " + " | ".join(header) + " |",
          "|" + "|".join(["---"] * len(header)) + "|"]
    for row in rows:
        md.append("| " + " | ".join(row) + " |")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(md), encoding="utf-8")
    print(f"\nBenchmark table written to {out_path}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="ChemAgent evaluation runner")
    ap.add_argument("--quick",   action="store_true", help="Only Q1+Q2 (smoke)")
    ap.add_argument("--query",   help="Single query id (Q1..Q8)")
    ap.add_argument("--out",     default="evaluation/results.md")
    ap.add_argument("--profile", default=None, help="Single model profile name")
    ap.add_argument("--judge",   default=None, help="Model profile to use as LLM judge")
    ap.add_argument(
        "--models", default=None,
        help="Comma-separated profiles for benchmark mode "
             "(e.g. 'claude_haiku,local_gemma_e2b')",
    )
    args = ap.parse_args()

    queries = EVAL_QUERIES
    if args.query:
        queries = [q for q in EVAL_QUERIES if q["id"].lower() == args.query.lower()]
        if not queries:
            print(f"Unknown query id: {args.query}")
            sys.exit(2)
    elif args.quick:
        queries = EVAL_QUERIES[:2]

    if args.models:
        model_names = [m.strip() for m in args.models.split(",")]
        bench_path = Path(args.out).parent / "benchmark_results.md"
        sys.exit(run_benchmark(queries, model_names, args.judge, bench_path))
    else:
        exit_code, _ = run(queries, Path(args.out),
                           model_profile=args.profile, judge_profile=args.judge)
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
