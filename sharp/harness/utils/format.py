"""Output formatting utilities."""

from __future__ import annotations

from sharp.harness.core.types import ToolResult


def format_tool_result(result: ToolResult) -> str:
    """Format a tool result for display."""
    status = "✓" if result.success else "✗"
    parts = [f"[{status}] {result.tool_name}"]
    if result.output:
        parts.append(f"  Output: {result.output[:200]}")
    if result.error:
        parts.append(f"  Error: {result.error}")
    if result.duration_ms > 0:
        parts.append(f"  Duration: {result.duration_ms:.0f}ms")
    return "\n".join(parts)


def format_signal(signal_type: str, message: str, fix_instructions: str = "") -> str:
    """Format a harness signal as XML for LLM consumption."""
    parts = [f"<harness:signal type=\"{signal_type}\">"]
    parts.append(f"  <message>{message}</message>")
    if fix_instructions:
        parts.append(f"  <fix_instructions>{fix_instructions}</fix_instructions>")
    parts.append("</harness:signal>")
    return "\n".join(parts)


def truncate_output(output: str, max_length: int = 2000) -> str:
    """Truncate output to a maximum length with indicator."""
    if len(output) <= max_length:
        return output
    return output[: max_length - 50] + "\n\n... [truncated, full output was {} chars]".format(len(output))
