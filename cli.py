"""CLI entry point for the harness system."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sharp import HarnessEngine, HarnessConfig

app = typer.Typer(
    name="harness",
    help="Harness System - A production-grade harness for LLM agents",
    add_completion=False,
)
console = Console()


@app.command()
def run(
    request: str = typer.Argument(..., help="The request to process"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override LLM model"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Run a request through the harness system."""
    # Load config
    if config:
        harness_config = HarnessConfig.from_yaml(config)
    else:
        harness_config = HarnessConfig.default()

    # Override model if specified
    if model:
        harness_config.llm.model = model

    # Setup logging
    if verbose:
        from sharp.harness.observability.logging import setup_logging
        setup_logging("DEBUG")

    engine = HarnessEngine(harness_config)

    # Run
    console.print(Panel(f"[bold blue]Processing:[/bold blue] {request}"))

    result = asyncio.run(engine.run(request))

    if result.success:
        console.print(Panel(result.output, title="[bold green]Response[/bold green]"))
        console.print(
            f"\n[dim]Attempts: {result.attempts} | "
            f"Latency: {result.total_latency_ms:.0f}ms | "
            f"Cost: ${result.total_cost_usd:.4f} | "
            f"Tokens: {result.total_tokens}[/dim]"
        )
    else:
        console.print(Panel(f"[red]{result.error}[/red]", title="[bold red]Error[/bold red]"))


@app.command()
def validate(
    response: str = typer.Argument(..., help="Response to validate"),
    request: str = typer.Option(..., "--request", "-r", help="Original request"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """Validate a response without running the full pipeline."""
    harness_config = HarnessConfig.from_yaml(config) if config else HarnessConfig.default()
    engine = HarnessEngine(harness_config)

    result = engine.validator.validate(
        response=response,
        user_request=request,
    )

    table = Table(title="Validation Result")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Passed", "✓" if result.passed else "✗")
    table.add_row("Score", f"{result.score:.2f}")
    table.add_row("Feedback", result.feedback)
    table.add_row("Issues", "\n".join(result.issues) or "None")
    table.add_row("Suggestions", "\n".join(result.suggestions) or "None")

    console.print(table)


@app.command()
def config_show() -> None:
    """Show the default configuration."""
    config = HarnessConfig.default()
    console.print_json(config.model_dump_json(indent=2))


@app.command()
def health() -> None:
    """Check system health."""
    from sharp.harness.safety.circuit_breaker import CircuitBreaker
    from sharp.harness.safety.budget import BudgetManager

    table = Table(title="System Health")
    table.add_column("Component")
    table.add_column("Status")

    # Circuit breaker
    cb = CircuitBreaker(HarnessConfig.default().safety)
    table.add_row("Circuit Breaker", f"✓ {cb.state}")

    # Budget
    bm = BudgetManager(HarnessConfig.default().safety)
    usage = bm.get_usage()
    table.add_row("Budget", f"✓ ${usage['session_cost']:.4f} / ${usage['cost_limit']:.2f}")

    # LLM Provider
    try:
        import litellm
        table.add_row("LiteLLM", "✓ installed")
    except ImportError:
        table.add_row("LiteLLM", "✗ not installed")

    console.print(table)


if __name__ == "__main__":
    app()
