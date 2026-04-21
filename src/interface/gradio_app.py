"""
ChemAgent Gradio interface: event-aware conversational analytics workspace.

Tab 1: Chat   : streaming agent Q&A, linked Plotly chart, tool trace
Tab 2: Explore: direct tool testing with interactive chart
Tab 3: Eval   : QA table with verdicts against ground truth
"""

from __future__ import annotations

from pathlib import Path

import gradio as gr
from smolagents.agents import ActionStep, FinalAnswerStep

from ..agent.chem_agent import build_agent
from ..model_registry import ModelRegistry
from ..data.loader import load_timeseries, load_events, T_MAX
from ..data.query_utils import VALID_COLUMNS
from ..tools.summary_statistics import summary_statistics
from ..tools.compute_trend import compute_trend
from ..tools.plot_variable import plot_variable
from .chart import (
    build_chart,
    VAR_CHOICES,
    VAR_CHOICE_TO_COL,
    DEFAULT_VAR_CHOICES,
    EVENTS,
)

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

CSS = """
/* ── Global ── */
.gradio-container { max-width: 1440px !important; font-family: 'Inter', system-ui, sans-serif !important; }

/* ── Header ── */
#ca-header {
    background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
    color: white; padding: 18px 24px; border-radius: 12px;
    margin-bottom: 12px; box-shadow: 0 4px 12px rgba(30,27,75,0.25);
}
#ca-header h2 { margin: 0 0 4px; font-size: 1.35em; font-weight: 700; }
#ca-header p  { margin: 0; opacity: 0.75; font-size: 0.88em; }
.ca-event-badges { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
.ca-event-badge  {
    padding: 3px 10px; border-radius: 20px; font-size: 0.78em;
    font-weight: 600; border: 1px solid;
}
.ca-kpi-row { display: flex; gap: 16px; margin-top: 10px; flex-wrap: wrap; }
.ca-kpi     { font-size: 0.78em; opacity: 0.7; }

/* ── Status pill ── */
#ca-status textarea {
    font-size: 0.82em !important; color: #6366f1 !important;
    background: #eef2ff !important; border: 1px solid #c7d2fe !important;
    border-radius: 20px !important; padding: 4px 14px !important;
    min-height: unset !important; line-height: 1.4 !important;
}

/* ── Tool trace ── */
#ca-trace { background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 8px; padding: 4px 0; }

/* ── Chatbot ── */
#ca-chatbot { border-radius: 12px !important; }

/* ── Quick example buttons ── */
.ca-example-btn button {
    font-size: 0.82em !important; padding: 4px 10px !important;
    background: #f1f5f9 !important; border: 1px solid #e2e8f0 !important;
    color: #475569 !important; border-radius: 20px !important;
}
.ca-example-btn button:hover {
    background: #e0e7ff !important; border-color: #6366f1 !important;
    color: #4338ca !important;
}

/* ── Variable selector ── */
#ca-var-selector .wrap { display: flex; flex-wrap: wrap; gap: 4px; }
#ca-var-selector label { font-size: 0.82em !important; }

/* ── Section labels ── */
.ca-section-label {
    font-size: 0.75em; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.05em; color: #94a3b8; margin: 8px 0 4px;
}

/* ── Eval table ── */
#ca-eval-table table { font-size: 0.85em; }
#ca-eval-table th { background: #f1f5f9; font-weight: 600; }
"""

# ---------------------------------------------------------------------------
# Header HTML
# ---------------------------------------------------------------------------

def _build_header() -> str:
    df = load_timeseries()
    n_pts = len(df)
    return f"""
<div id="ca-header">
  <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:12px;">
    <div>
      <h2>ChemAgent</h2>
      <p>Natural-language queries over a 72-hour continuous bioreactor run.</p>
    </div>
    <div class="ca-event-badges">
      <span class="ca-event-badge"
            style="color:#fde68a; background:rgba(245,158,11,0.2); border-color:#f59e0b;">
        Feed adj. 30 h
      </span>
      <span class="ca-event-badge"
            style="color:#a5f3fc; background:rgba(6,182,212,0.2); border-color:#06b6d4;">
        O₂ limit 38–42 h
      </span>
      <span class="ca-event-badge"
            style="color:#c7d2fe; background:rgba(99,102,241,0.2); border-color:#6366f1;">
        pH drift 42–72 h
      </span>
    </div>
  </div>
  <div class="ca-kpi-row">
    <span class="ca-kpi">72 h run</span>
    <span class="ca-kpi">7 variables</span>
    <span class="ca-kpi">1-min sampling</span>
    <span class="ca-kpi">3 events</span>
    <span class="ca-kpi">{n_pts:,} data points</span>
  </div>
</div>
"""


# ---------------------------------------------------------------------------
# Evaluation query set
# ---------------------------------------------------------------------------

EVAL_QUERIES = [
    {
        "id": "Q1", "type": "Descriptive",
        "question": "What was the average pH over the last 12 hours?",
        "expected": "Mean ~6.99 [6.95–7.05]. Must flag sensor drift.",
        "verdict": "", "justification": "",
    },
    {
        "id": "Q2", "type": "Descriptive",
        "question": "What was the maximum biomass concentration between 20 h and 36 h?",
        "expected": "~15.0 g/L (range 14.5–15.5).",
        "verdict": "", "justification": "",
    },
    {
        "id": "Q3", "type": "Descriptive",
        "question": "What was the minimum dissolved oxygen in the first 24 hours?",
        "expected": "~59.8 % (range 58–62 %). Should NOT mention later O2 limitation.",
        "verdict": "", "justification": "",
    },
    {
        "id": "Q4", "type": "Diagnostic",
        "question": "Were there any temperature anomalies after 24 h?",
        "expected": "No large anomalies; minor +0.4 °C transient during O2 limitation.",
        "verdict": "", "justification": "",
    },
    {
        "id": "Q5", "type": "Diagnostic",
        "question": "Did dissolved oxygen show an unusual drop near 38 h?",
        "expected": "Yes: drop ~65% → ~33.7%, dip ~31 pp during [38, 42) h.",
        "verdict": "", "justification": "",
    },
    {
        "id": "Q6", "type": "Diagnostic",
        "question": "Was there evidence of pH drift after 42 h?",
        "expected": "Yes: upward drift ~0.008 pH/h. Must flag as sensor fault.",
        "verdict": "", "justification": "",
    },
    {
        "id": "Q7", "type": "Comparative",
        "question": "How did product titer change before and after the feed adjustment?",
        "expected": "Pre-slope ~0.19, post-slope ~0.35 g/L/h; ratio ~1.8× (1.5–2.2× acceptable).",
        "verdict": "", "justification": "",
    },
    {
        "id": "Q8", "type": "Comparative",
        "question": "How did substrate concentration change after the oxygen limitation event?",
        "expected": "Decrease ~1.8 g/L (~23%); pre ~7.59 g/L, post ~5.83 g/L.",
        "verdict": "", "justification": "",
    },
]

_EVAL_DISPLAY_COLS = ["id", "type", "question", "expected", "verdict", "justification"]

# ---------------------------------------------------------------------------
# Agent cache (keyed by profile name)
# ---------------------------------------------------------------------------

_registry = ModelRegistry()
_agent_cache: dict[str, object] = {}


def get_agent(profile: str | None = None):
    effective = profile or _registry.default_name()
    if effective not in _agent_cache:
        _agent_cache[effective] = build_agent(effective)
    return _agent_cache[effective]


def reset_agent() -> None:
    _agent_cache.clear()


def _friendly_error(e: Exception) -> str:
    msg = str(e)
    if "charmap" in msg or "encode" in msg:
        return "Agent error: encoding issue. Please try again."
    if "rate" in msg.lower() or "429" in msg:
        return "Agent error: API rate limit hit. Wait a moment and retry."
    if "api" in msg.lower() or "auth" in msg.lower():
        return "Agent error: API key issue. Check your .env file."
    return f"Agent error: {msg}"


# ---------------------------------------------------------------------------
# Tab 1: Chat: streaming handler
# ---------------------------------------------------------------------------

def chat_with_image(message: str, history: list, var_choices: list[str], model_profile: str | None = None):
    """
    Streaming chat handler.
    Yields: (msg_box, chatbot, chart_plot, status_text, tool_trace_md)
    """
    if not message.strip():
        yield "", history, build_chart(var_choices), "", ""
        return

    history = history + [{"role": "user", "content": message}]
    yield "", history, build_chart(var_choices), "Thinking...", ""

    agent = get_agent(model_profile)
    tool_calls_log: list[str] = []
    highlight_t_start = highlight_t_end = None
    analysis_col: str | None = None

    try:
        step_num = 0
        for event in agent.run(message, stream=True):

            if isinstance(event, ActionStep):
                step_num += 1

                if event.tool_calls:
                    tc = event.tool_calls[0]
                    args = tc.arguments or {}
                    args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
                    status = f"Step {step_num}: {tc.name}({args_str})"

                    # Capture analysis window from first tool with t_start/t_end
                    if highlight_t_start is None:
                        if "t_start" in args and "t_end" in args:
                            highlight_t_start = float(args["t_start"])
                            highlight_t_end   = float(args["t_end"])
                        if "column" in args:
                            analysis_col = str(args["column"])

                    # Log for trace accordion
                    result_preview = ""
                    if event.action_output is not None:
                        rp = str(event.action_output)
                        result_preview = rp[:120] + "..." if len(rp) > 120 else rp
                    tool_calls_log.append(
                        f"**Step {step_num}** `{tc.name}`: `{args_str}`\n"
                        f"> {result_preview}"
                    )
                else:
                    status = f"Step {step_num}: processing..."

                yield "", history, build_chart(var_choices), status, ""

            elif isinstance(event, FinalAnswerStep):
                final_text = str(event.output)

                # Build updated chart with analysis window highlighted
                chart_cols = var_choices[:]
                if analysis_col:
                    choice = next(
                        (k for k, v in VAR_CHOICE_TO_COL.items() if v == analysis_col),
                        None,
                    )
                    if choice and choice not in chart_cols:
                        chart_cols = [choice] + chart_cols

                updated_chart = build_chart(
                    chart_cols,
                    highlight_t_start=highlight_t_start,
                    highlight_t_end=highlight_t_end,
                )

                # Tool trace markdown
                trace_md = "\n\n---\n\n".join(tool_calls_log) if tool_calls_log else ""

                final_history = history + [{"role": "assistant", "content": final_text}]
                yield "", final_history, updated_chart, "Done", trace_md
                return

    except Exception as e:
        err_history = history + [{"role": "assistant", "content": _friendly_error(e)}]
        yield "", err_history, build_chart(var_choices), "Error", ""


# ---------------------------------------------------------------------------
# Chart update helpers
# ---------------------------------------------------------------------------

def update_chart_vars(var_choices: list[str]):
    return build_chart(var_choices)


def focus_chart_range(var_choices: list[str], t_start: float, t_end: float):
    fig = build_chart(var_choices, x_range=(t_start, t_end))
    return fig


def focus_chart_event(var_choices: list[str], event_idx: int):
    ev = EVENTS[event_idx]
    pad = 4.0
    x0 = max(0, ev["t_start"] - pad)
    x1 = min(72, ev["t_end"] + pad)
    fig = build_chart(
        var_choices,
        highlight_t_start=ev["t_start"],
        highlight_t_end=ev["t_end"],
        x_range=(x0, x1),
    )
    return fig


# ---------------------------------------------------------------------------
# Tab 2: Explore helpers
# ---------------------------------------------------------------------------

def explore(column: str, t_start: float, t_end: float):
    try:
        stats = summary_statistics(column, t_start, t_end)
        trend = compute_trend(column, t_start, t_end)
        text  = f"{stats}\n\n{trend}"
        # Build focused chart
        choice = next(
            (k for k, v in VAR_CHOICE_TO_COL.items() if v == column), "pH"
        )
        chart = build_chart(
            [choice],
            highlight_t_start=t_start,
            highlight_t_end=t_end,
            x_range=(max(0, t_start - 2), min(72, t_end + 2)),
        )
        return text, chart
    except ValueError as e:
        return f"Error: {e}", build_chart()
    except Exception as e:
        return f"Unexpected error: {e}", build_chart()


# ---------------------------------------------------------------------------
# Tab 3: Eval helpers
# ---------------------------------------------------------------------------

def _eval_table_data() -> list[list]:
    return [[q["id"], q["type"], q["question"], q["expected"], q["verdict"], q["justification"]]
            for q in EVAL_QUERIES]


def run_single_eval(selected_rows):
    """Run one query (first selected row in the table) through the agent."""
    if not selected_rows:
        return _eval_table_data(), "Select a row first."
    row_idx = selected_rows[0] if isinstance(selected_rows[0], int) else 0
    q = EVAL_QUERIES[row_idx]
    agent = get_agent()
    try:
        answer = str(agent.run(q["question"]))
    except Exception as e:
        answer = _friendly_error(e)
    return answer, q["expected"]


def run_all_evals(model_profile: str | None = None) -> str:
    agent = get_agent(model_profile)
    lines = ["# ChemAgent: Evaluation Results\n"]
    for q in EVAL_QUERIES:
        lines.append(f"## {q['id']} ({q['type']})")
        lines.append(f"**Q:** {q['question']}\n")
        try:
            answer = str(agent.run(q["question"]))
        except Exception as e:
            answer = _friendly_error(e)
        lines.append(f"**Agent answer:** {answer}\n")
        lines.append(f"**Expected:** {q['expected']}\n")
        lines.append("---\n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# App layout
# ---------------------------------------------------------------------------

def build_app() -> gr.Blocks:

    with gr.Blocks(title="ChemAgent") as app:

        # ── Header ────────────────────────────────────────────────────────
        gr.HTML(_build_header())

        with gr.Row():
            model_selector = gr.Dropdown(
                choices=_registry.dropdown_choices(),
                value=_registry.default_name(),
                label="Model profile",
                scale=1,
                interactive=True,
                info="Switch backend: changes take effect on next query",
            )
            model_status = gr.Textbox(
                value=f"Active: {_registry.get(_registry.default_name()).label}",
                show_label=False,
                interactive=False,
                scale=3,
            )

        with gr.Tabs():

            # ==============================================================
            # Tab 1: Chat
            # ==============================================================
            with gr.Tab("Chat"):

                with gr.Row(equal_height=False):

                    # ── LEFT: conversation column ─────────────────────────
                    with gr.Column(scale=56, min_width=400):

                        chatbot = gr.Chatbot(
                            height=440,
                            label="ChemAgent",
                            show_label=False,
                            elem_id="ca-chatbot",
                            placeholder=(
                                "**Start with an event, a variable, or a question.**\n\n"
                                "Each answer is tied to a time window and linked to the chart."
                            ),
                        )

                        with gr.Accordion(
                            "Tool trace", open=False, elem_id="ca-trace"
                        ) as trace_accordion:
                            tool_trace_md = gr.Markdown("", elem_id="ca-trace-content")

                        status_bar = gr.Textbox(
                            value="",
                            show_label=False,
                            elem_id="ca-status",
                            interactive=False,
                            lines=1, max_lines=1,
                            placeholder="Agent status...",
                        )

                        msg_box = gr.Textbox(
                            placeholder="Ask a question about the bioreactor run...",
                            label="Your question",
                            lines=2,
                            autofocus=True,
                        )

                        with gr.Row():
                            submit_btn = gr.Button("Ask", variant="primary", scale=3)
                            clear_btn  = gr.Button("Clear", scale=1)

                        # Variable selector
                        gr.HTML("<div class='ca-section-label'>Variables to display</div>")
                        var_selector = gr.CheckboxGroup(
                            choices=VAR_CHOICES,
                            value=DEFAULT_VAR_CHOICES,
                            label="",
                            elem_id="ca-var-selector",
                        )

                        # Event shortcuts
                        gr.HTML("<div class='ca-section-label'>Event shortcuts</div>")
                        with gr.Row():
                            ev1_btn = gr.Button("Feed adj. 30 h",   size="sm", elem_classes="ca-example-btn")
                            ev2_btn = gr.Button("O2 limit 38–42 h", size="sm", elem_classes="ca-example-btn")
                            ev3_btn = gr.Button("pH drift 42–72 h", size="sm", elem_classes="ca-example-btn")

                        # Example prompts
                        gr.HTML("<div class='ca-section-label'>Example queries</div>")
                        with gr.Row():
                            ex1 = gr.Button("Avg pH last 12 h",            size="sm", elem_classes="ca-example-btn")
                            ex2 = gr.Button("Min DO first 24 h",           size="sm", elem_classes="ca-example-btn")
                            ex3 = gr.Button("DO drop near 38 h?",          size="sm", elem_classes="ca-example-btn")
                        with gr.Row():
                            ex4 = gr.Button("pH drift after 42 h?",        size="sm", elem_classes="ca-example-btn")
                            ex5 = gr.Button("Titer change after feed adj?", size="sm", elem_classes="ca-example-btn")
                            ex6 = gr.Button("Plot biomass full run",        size="sm", elem_classes="ca-example-btn")

                    # ── RIGHT: chart column ───────────────────────────────
                    with gr.Column(scale=44, min_width=360):

                        chart_plot = gr.Plot(
                            label="Time Series",
                            show_label=False,
                            value=build_chart(DEFAULT_VAR_CHOICES),
                        )

                        # Time range presets
                        gr.HTML("<div class='ca-section-label'>Time range</div>")
                        with gr.Row():
                            tr_full = gr.Button("Full run",  size="sm", elem_classes="ca-example-btn")
                            tr_0_24 = gr.Button("0–24 h",   size="sm", elem_classes="ca-example-btn")
                            tr_24_48= gr.Button("24–48 h",  size="sm", elem_classes="ca-example-btn")
                            tr_48_72= gr.Button("48–72 h",  size="sm", elem_classes="ca-example-btn")

                # ── Event wiring ──────────────────────────────────────────

                # Chat submit
                chat_outputs = [msg_box, chatbot, chart_plot, status_bar, tool_trace_md]

                submit_btn.click(
                    chat_with_image,
                    inputs=[msg_box, chatbot, var_selector, model_selector],
                    outputs=chat_outputs,
                )
                msg_box.submit(
                    chat_with_image,
                    inputs=[msg_box, chatbot, var_selector, model_selector],
                    outputs=chat_outputs,
                )
                clear_btn.click(
                    lambda vs: ([], build_chart(vs), "", ""),
                    inputs=[var_selector],
                    outputs=[chatbot, chart_plot, status_bar, tool_trace_md],
                )

                # Variable selector → update chart
                var_selector.change(
                    update_chart_vars,
                    inputs=[var_selector],
                    outputs=[chart_plot],
                )

                # Time range buttons
                tr_full.click(lambda vs: focus_chart_range(vs, 0, 72),    inputs=[var_selector], outputs=[chart_plot])
                tr_0_24.click(lambda vs: focus_chart_range(vs, 0, 24),    inputs=[var_selector], outputs=[chart_plot])
                tr_24_48.click(lambda vs: focus_chart_range(vs, 24, 48),  inputs=[var_selector], outputs=[chart_plot])
                tr_48_72.click(lambda vs: focus_chart_range(vs, 48, 72),  inputs=[var_selector], outputs=[chart_plot])

                # Event shortcut buttons: prefill prompt + focus chart on event
                ev1_btn.click(
                    lambda vs: ("Compare product titer 6 h before and after the feed adjustment at 30 h", focus_chart_event(vs, 0)),
                    inputs=[var_selector], outputs=[msg_box, chart_plot],
                )
                ev2_btn.click(
                    lambda vs: ("Did dissolved oxygen show an unusual drop near 38 h?", focus_chart_event(vs, 1)),
                    inputs=[var_selector], outputs=[msg_box, chart_plot],
                )
                ev3_btn.click(
                    lambda vs: ("Was there evidence of pH drift after 42 h?", focus_chart_event(vs, 2)),
                    inputs=[var_selector], outputs=[msg_box, chart_plot],
                )

                # Example query buttons
                ex1.click(lambda: "What was the average pH over the last 12 hours?",                outputs=msg_box)
                ex2.click(lambda: "What was the minimum dissolved oxygen in the first 24 hours?",   outputs=msg_box)
                ex3.click(lambda: "Did dissolved oxygen show an unusual drop near 38 h?",           outputs=msg_box)
                ex4.click(lambda: "Was there evidence of pH drift after 42 h?",                    outputs=msg_box)
                ex5.click(lambda: "How did product titer change before and after the feed adjustment?", outputs=msg_box)
                ex6.click(lambda: "Plot biomass concentration for the full run",                   outputs=msg_box)

            # ==============================================================
            # Tab 2: Explore
            # ==============================================================
            with gr.Tab("Explore"):
                gr.Markdown(
                    "Directly inspect any variable and time window. "
                    "No agent: raw tool output with linked chart."
                )
                with gr.Row():
                    col_dd  = gr.Dropdown(
                        choices=sorted(VALID_COLUMNS), value="ph", label="Variable",
                    )
                    t_start = gr.Slider(0.0, T_MAX, value=0.0,  step=1.0, label="t_start (h)")
                    t_end   = gr.Slider(0.0, T_MAX, value=72.0, step=1.0, label="t_end (h)")
                    run_btn = gr.Button("Run", variant="primary")

                with gr.Row():
                    with gr.Column(scale=1):
                        stats_box = gr.Textbox(label="Statistics + Trend", lines=14)
                    with gr.Column(scale=2):
                        explore_chart = gr.Plot(label="Chart", value=build_chart())

                run_btn.click(
                    explore,
                    inputs=[col_dd, t_start, t_end],
                    outputs=[stats_box, explore_chart],
                )

            # ==============================================================
            # Tab 3: Evaluation
            # ==============================================================
            with gr.Tab("Evaluation"):
                gr.Markdown(
                    "Eight evaluation queries covering descriptive, diagnostic, and comparative "
                    "query classes. Select a query and run it, or run all 8."
                )

                with gr.Row():
                    query_dd    = gr.Dropdown(
                        choices=[f"{q['id']}: {q['question'][:60]}..." for q in EVAL_QUERIES],
                        value=f"{EVAL_QUERIES[0]['id']}: {EVAL_QUERIES[0]['question'][:60]}...",
                        label="Select query",
                        scale=4,
                    )
                    run_one_btn = gr.Button("Run selected", variant="primary", scale=1)
                    run_all_btn = gr.Button("Run all 8",    variant="secondary", scale=1)

                with gr.Row():
                    answer_box   = gr.Textbox(label="Agent answer",            lines=8)
                    expected_box = gr.Textbox(label="Expected (ground truth)", lines=8)

                full_report = gr.Markdown(label="Full evaluation report")

                def _run_selected(label: str, model_profile: str | None = None):
                    idx = next(
                        (i for i, q in enumerate(EVAL_QUERIES)
                         if label.startswith(q["id"])),
                        0,
                    )
                    q = EVAL_QUERIES[idx]
                    agent = get_agent(model_profile)
                    try:
                        answer = str(agent.run(q["question"]))
                    except Exception as e:
                        answer = _friendly_error(e)
                    return answer, q["expected"]

                run_one_btn.click(
                    _run_selected,
                    inputs=[query_dd, model_selector],
                    outputs=[answer_box, expected_box],
                )
                run_all_btn.click(
                    run_all_evals,
                    inputs=[model_selector],
                    outputs=[full_report],
                )

                def _on_model_change(profile: str) -> str:
                    reset_agent()
                    try:
                        label = _registry.get(profile).label
                    except Exception:
                        label = profile
                    return f"Active: {label}"

                model_selector.change(
                    _on_model_change,
                    inputs=[model_selector],
                    outputs=[model_status],
                )

    return app


def launch(share: bool = False, port: int = None) -> None:
    app = build_app()
    kwargs: dict = {
        "share": share,
        "theme": gr.themes.Soft(
            primary_hue="indigo",
            neutral_hue="slate",
            font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"],
        ),
        "css": CSS,
    }
    if port is not None:
        kwargs["server_port"] = port
    app.launch(**kwargs)


if __name__ == "__main__":
    launch()
