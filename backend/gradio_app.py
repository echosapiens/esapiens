"""
Gradio Chat Interface — Web UI for the E.sapiens agent.

Mounts alongside the FastAPI app at /gradio.
Provides a conversational chat interface using the same LangGraph
agent backend — no auth required for local/internal use.

Usage:
  from gradio_app import mount_gradio
  app = mount_gradio(fastapi_app)
"""

import os
import logging

logger = logging.getLogger(__name__)

# ── Import gradio (use `import gradio as gr`, NOT `from gradio import gr`) ─
# In Gradio 5+, the package root "gradio" IS the module.
# `from gradio import gr` only works in Gradio <4 and will fail with:
#   ImportError: cannot import name 'gr' from 'gradio'
# Always use: `import gradio as gr`
try:
    import gradio as gr

    GRADIO_AVAILABLE = True
except ImportError:
    GRADIO_AVAILABLE = False
    gr = None


def _build_interface() -> "gr.Blocks":
    """Build the Gradio Blocks interface for E.sapiens chat.

    Uses synchronous run() from main.py to keep it simple and avoid
    asyncio conflicts with Gradio's event loop.
    """
    if not GRADIO_AVAILABLE:
        raise RuntimeError("gradio is not installed")

    # Lazy-import the agent runtime — avoids circular imports at app.py level
    from main import run

    # ── Build the Blocks ─────────────────────────────────────────────
    # Note: Gradio 6 moved `theme` from Blocks() to launch()/mount_gradio_app()
    with gr.Blocks(
        title="E.sapiens — AI Bioinformatics Agent",
    ) as demo:
        gr.HTML(
            """<style>
        footer { display: none !important; }
        .gradio-container { max-width: 900px !important; margin: auto !important; }
        </style>"""
        )
        gr.Markdown(
            """
            # 🧬 E.sapiens
            ### AI-native bioinformatics agent
            Ask about genomic data, run analyses, explore public datasets.
            """
        )

        chatbot = gr.Chatbot(
            label="Conversation",
            placeholder="Ask a bioinformatics question...",
            height=500,
        )

        msg = gr.Textbox(
            label="Your question",
            placeholder="e.g., Find the PDB structure of human BRCA1 BRCT domain",
            lines=2,
            max_lines=6,
            scale=1,
        )

        with gr.Row():
            submit_btn = gr.Button("Submit", variant="primary", scale=1)
            clear_btn = gr.Button("Clear", scale=0)

        session_state = gr.State(value="default")

        # Show available modal tasks (if any)
        with gr.Accordion("Heavy Compute Tasks", open=False):
            gr.Markdown(
                """
                These tasks run on **Modal** cloud infrastructure via biocontainers:
                - **STAR Alignment** — RNA-seq read alignment
                - **SRA Download** — fetch FASTQ/SRA from NCBI
                - **DESeq2** — differential expression analysis
                - **GPU Pipelines** — ML tasks on GPU

                The agent dispatches to these automatically when needed.
                """
            )

        # ── Event handlers ────────────────────────────────────────────
        def respond(message: str, chat_history: list, sid: str) -> tuple:
            """Handle a user message, run the agent, return updated state."""
            if not message or not message.strip():
                return "", chat_history, sid

            # Keep a stable session per Gradio session
            if not sid or sid == "default":
                import uuid

                sid = f"gradio_{uuid.uuid4().hex[:8]}"

            chat_history = chat_history or []

            # Add user message immediately
            chat_history.append((message, None))

            try:
                result = run(query=message, session_id=sid)
                response_text = result.get("response", "")
                tool_calls = result.get("tool_calls", [])

                # Append tool info as a subtle detail if tools were used
                if tool_calls:
                    tool_summary = (
                        "  \n*Tools used: "
                        + ", ".join(t["name"] for t in tool_calls)
                        + "*"
                    )
                    response_text += tool_summary

                chat_history[-1] = (message, response_text)

            except Exception as e:
                logger.exception("Gradio agent error")
                error_msg = f"⚠️ Agent error: {str(e)}"
                chat_history[-1] = (message, error_msg)

            return "", chat_history, sid

        def clear_chat() -> tuple:
            """Reset chat and generate a new session."""
            import uuid

            new_sid = f"gradio_{uuid.uuid4().hex[:8]}"
            return [], new_sid

        # Wire up events
        msg.submit(
            respond, [msg, chatbot, session_state], [msg, chatbot, session_state]
        )
        submit_btn.click(
            respond, [msg, chatbot, session_state], [msg, chatbot, session_state]
        )
        clear_btn.click(clear_chat, None, [chatbot, session_state])

    return demo


def mount_gradio(app) -> object:
    """Mount the Gradio interface onto a FastAPI app at /gradio.

    Args:
        app: A FastAPI application instance.

    Returns:
        The FastAPI app with Gradio mounted (or unchanged if gradio
        is unavailable).
    """
    if not GRADIO_AVAILABLE:
        logger.warning("gradio not installed — skipping /gradio mount")
        return app

    mount_path = os.environ.get("GRADIO_MOUNT_PATH", "/gradio")
    demo = _build_interface()
    gr.mount_gradio_app(
        app,
        demo,
        path=mount_path,
        theme=gr.themes.Soft(primary_hue="blue", neutral_hue="slate"),
    )
    logger.info("Gradio interface mounted at %s", mount_path)
    return app
