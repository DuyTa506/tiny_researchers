"""
Claw Researcher CLI.

Usage:
  claw chat          → Interactive research chat (main mode)
  claw status        → Check configuration and API availability
  claw onboard       → Initialize workspace with skills and memory
  claw serve         → Start multi-channel interactive server
"""

from __future__ import annotations

import asyncio
import sys

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

app = typer.Typer(
    name="claw",
    help="Claw Researcher — AI Agent for Academic Research",
    add_completion=False,
)
console = Console()


@app.command()
def chat(
    model: str = typer.Option("", help="Override LLM model"),
    workspace: str = typer.Option(".", help="Workspace directory"),
):
    """Start an interactive research chat session."""
    asyncio.run(_chat_loop(model=model, workspace=workspace))


async def _chat_loop(model: str = "", workspace: str = "."):
    """Main chat REPL."""
    from pathlib import Path
    from claw.agent.loop import AgentLoop
    from claw.agent.providers import LLMProvider
    from claw.config import get_settings

    settings = get_settings()
    ws = Path(workspace).resolve()
    settings.ensure_workspace()

    provider = LLMProvider(
        model=model or settings.default_model,
        api_key=settings.anthropic_api_key or None,
    )

    agent = AgentLoop(
        workspace=ws,
        provider=provider,
        model=model or settings.default_model,
        max_iterations=settings.max_iterations,
        context_window_tokens=settings.context_window_tokens,
    )

    # Welcome message
    console.print(Panel(
        "[bold]Claw Researcher[/bold] 🧠\n"
        f"Model: {agent.model}\n"
        f"Workspace: {ws}\n"
        f"Tools: {len(agent.tools)} | Skills: {len(agent.context.skills.list_skills())}\n\n"
        "Type your research question or /help for commands.",
        title="Welcome",
        border_style="blue",
    ))

    async def on_progress(text: str):
        if text.startswith("🔧"):
            console.print(f"  [dim]{text}[/dim]")
        else:
            console.print(f"  [italic dim]{text[:120]}[/italic dim]")

    while True:
        try:
            user_input = console.input("\n[bold blue]You:[/bold blue] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("/quit", "/exit", "exit", "quit"):
            console.print("[dim]Goodbye![/dim]")
            break

        console.print()
        try:
            response = await agent.chat(user_input, on_progress=on_progress)
            console.print()
            console.print(Panel(Markdown(response), title="Claw", border_style="green"))
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/yellow]")
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")


@app.command()
def onboard(
    workspace: str = typer.Option(".", help="Workspace directory"),
):
    """Initialize workspace with memory templates and skills."""
    from pathlib import Path
    from claw.config import get_settings

    settings = get_settings()
    ws = Path(workspace).resolve()
    settings.ensure_workspace()

    # Copy builtin skills to workspace if not present
    from claw.agent.skills import BUILTIN_SKILLS_DIR
    import shutil

    ws_skills = ws / "skills"
    ws_skills.mkdir(exist_ok=True)

    if BUILTIN_SKILLS_DIR.exists():
        for skill_dir in BUILTIN_SKILLS_DIR.iterdir():
            if skill_dir.is_dir():
                dest = ws_skills / skill_dir.name
                if not dest.exists():
                    shutil.copytree(skill_dir, dest)
                    console.print(f"  [green]✓[/green] Installed skill: {skill_dir.name}")
                else:
                    console.print(f"  [dim]⊘[/dim] Skill exists: {skill_dir.name}")

    # Initialize memory
    from claw.agent.memory import MemoryStore
    store = MemoryStore(ws)
    console.print(f"  [green]✓[/green] Memory initialized: {store.memory_file}")

    console.print(Panel(
        f"Workspace: {ws}\n"
        f"Skills: {ws_skills}\n"
        f"Memory: {ws / 'memory'}\n\n"
        "Run [bold]claw chat[/bold] to start researching!",
        title="✅ Onboarding Complete",
        border_style="green",
    ))


@app.command()
def status():
    """Check system status and API configuration."""
    import os
    from claw.config import get_settings

    settings = get_settings()

    console.print("[bold]🧠 Claw Researcher Status[/bold]\n")
    console.print(f"  Workspace: {settings.workspace}")
    console.print(f"  Model: {settings.default_model}")
    console.print()

    checks = {
        "ANTHROPIC_API_KEY": bool(settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")),
        "Semantic Scholar API": bool(settings.semantic_scholar_api_key),
        "litellm installed": _check_import("litellm"),
        "httpx installed": _check_import("httpx"),
        "loguru installed": _check_import("loguru"),
        "rich installed": _check_import("rich"),
    }

    for name, ok in checks.items():
        icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
        console.print(f"  {icon} {name}")


def _check_import(module: str) -> bool:
    try:
        __import__(module)
        return True
    except ImportError:
        return False


@app.command()
def serve(
    workspace: str = typer.Option(".", help="Workspace directory"),
    config_file: str = typer.Option("channels.json", help="Channel config file name"),
    webhook_host: str = typer.Option("0.0.0.0", help="Webhook server host"),
    webhook_port: int = typer.Option(8080, help="Webhook server port"),
):
    """Start the multi-channel interactive server."""
    asyncio.run(
        _serve_loop(
            workspace=workspace,
            config_file=config_file,
            webhook_host=webhook_host,
            webhook_port=webhook_port,
        )
    )


async def _serve_loop(
    workspace: str,
    config_file: str,
    webhook_host: str,
    webhook_port: int,
) -> None:
    """Async serve loop: load config, build agent+gateway, start serving."""
    import json
    import signal
    from pathlib import Path
    from claw.agent.loop import AgentLoop
    from claw.agent.providers import LLMProvider
    from claw.config import get_settings
    from claw.interactive.gateway import InteractiveGateway, _write_channels_template

    settings = get_settings()
    ws = Path(workspace).resolve()
    settings.ensure_workspace()

    config_path = ws / config_file

    if not config_path.exists():
        # Create template channels.json and exit with instructions
        _write_channels_template(config_path)
        console.print(
            Panel(
                f"[bold]channels.json template created at:[/bold]\n  {config_path}\n\n"
                "Edit it with your tokens then run:\n"
                f"  [bold]claw serve --workspace {workspace}[/bold]",
                title="⚙️  First-time Setup",
                border_style="yellow",
            )
        )
        return

    try:
        configs = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as e:
        console.print(f"[red]Failed to load {config_path}: {e}[/red]")
        raise typer.Exit(1)

    # Build agent
    provider = LLMProvider(
        model=settings.default_model,
        api_key=settings.anthropic_api_key or None,
    )
    agent = AgentLoop(
        workspace=ws,
        provider=provider,
        model=settings.default_model,
        max_iterations=settings.max_iterations,
        context_window_tokens=settings.context_window_tokens,
    )

    # Build gateway
    gateway = InteractiveGateway(
        agent=agent,
        configs=configs,
        webhook_host=webhook_host,
        webhook_port=webhook_port,
    )

    enabled_channels = list(gateway.channels.keys())
    if not enabled_channels:
        console.print(
            "[yellow]No channels are enabled in channels.json. "
            "Set 'enabled: true' for at least one channel.[/yellow]"
        )
        return

    console.print(
        Panel(
            f"[bold green]Claw multi-channel server starting...[/bold green]\n"
            f"Workspace: {ws}\n"
            f"Channels: {', '.join(enabled_channels)}\n"
            f"Webhook: http://{webhook_host}:{webhook_port}\n\n"
            "Press Ctrl+C to stop.",
            title="🐾 Claw Serve",
            border_style="green",
        )
    )

    loop = asyncio.get_running_loop()

    def _handle_shutdown() -> None:
        console.print("\n[yellow]Shutting down...[/yellow]")
        asyncio.create_task(gateway.stop())

    try:
        loop.add_signal_handler(signal.SIGINT, _handle_shutdown)
        loop.add_signal_handler(signal.SIGTERM, _handle_shutdown)
    except (NotImplementedError, AttributeError):
        # Windows doesn't support add_signal_handler for all signals
        pass

    try:
        await gateway.start()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await gateway.stop()
        console.print("[dim]Server stopped.[/dim]")


if __name__ == "__main__":
    app()
