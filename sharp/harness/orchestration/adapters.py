"""Interface adapters: normalize requests/responses from different AI interfaces.

Each adapter converts interface-specific formats into SHARP's normalized
InterfaceRequest/InterfaceResponse types.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sharp.harness.orchestration.types import (
    InterfaceRequest,
    InterfaceResponse,
    InterfaceType,
    ModelType,
    TaskType,
)
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


class InterfaceAdapter(ABC):
    """Base class for interface adapters.

    Each adapter normalizes:
    - Inbound: interface-specific request -> InterfaceRequest
    - Outbound: InterfaceResponse -> interface-specific response format
    """

    @property
    @abstractmethod
    def interface_type(self) -> InterfaceType:
        """Return the interface type this adapter handles."""
        ...

    @abstractmethod
    def normalize_request(self, raw_request: dict[str, Any]) -> InterfaceRequest:
        """Convert a raw request from this interface into a normalized InterfaceRequest."""
        ...

    @abstractmethod
    def format_response(self, response: InterfaceResponse) -> dict[str, Any]:
        """Convert a normalized InterfaceResponse into the format this interface expects."""
        ...

    def get_available_tools(self) -> list[str]:
        """Return list of tool names available to this interface."""
        return ["read_file", "list_directory", "search_files"]

    def get_max_context_tokens(self) -> int:
        """Return max context tokens for this interface."""
        return 8000


class ClaudeAppAdapter(InterfaceAdapter):
    """Adapter for Claude App (Mobile/Web) interface.

    Claude App has:
    - Good reasoning capability
    - Limited file system access (needs API)
    - No terminal access
    - Supports artifacts and code blocks
    """

    @property
    def interface_type(self) -> InterfaceType:
        return InterfaceType.CLAUDE_APP

    def normalize_request(self, raw_request: dict[str, Any]) -> InterfaceRequest:
        return InterfaceRequest(
            interface=InterfaceType.CLAUDE_APP,
            user_prompt=raw_request.get("prompt", raw_request.get("user_prompt", "")),
            task_type=self._infer_task_type(raw_request),
            context=raw_request.get("context", {}),
            files_involved=raw_request.get("files", []),
            repo_url=raw_request.get("repo_url"),
            session_id=raw_request.get("session_id"),
            user_id=raw_request.get("user_id"),
            metadata=raw_request.get("metadata", {}),
        )

    def format_response(self, response: InterfaceResponse) -> dict[str, Any]:
        """Format for Claude App: clean markdown with performance badge."""
        status_icon = "✅" if response.success else "❌"
        lines = [
            f"{status_icon} {response.output}",
            "",
            f"⏱️ {response.latency_ms/1000:.1f}s | 💰 ${response.cost_usd:.2f}",
        ]
        if response.retries > 0:
            lines.append(f"🔄 Retried {response.retries} time(s)")
        if response.validation_issues:
            lines.append(f"⚠️ Issues: {', '.join(response.validation_issues)}")

        return {
            "content": "\n".join(lines),
            "success": response.success,
            "latency_ms": response.latency_ms,
            "cost_usd": response.cost_usd,
            "model": response.model.value,
            "validation_passed": response.validation_passed,
        }

    def get_available_tools(self) -> list[str]:
        return ["read_file", "search_files", "web_search", "delegate_to_agent"]

    def get_max_context_tokens(self) -> int:
        return 100000  # Claude has large context window

    def _infer_task_type(self, raw: dict[str, Any]) -> TaskType | None:
        """Infer task type from raw request metadata."""
        if "task_type" in raw:
            try:
                return TaskType(raw["task_type"])
            except ValueError:
                pass
        return None


class ChatGPTAppAdapter(InterfaceAdapter):
    """Adapter for ChatGPT App (Mobile/Web) interface.

    ChatGPT App has:
    - Fast response generation
    - Good at summarization and retrieval
    - No file system access
    - No terminal access
    - GPT-4o / GPT-4o-mini models
    """

    @property
    def interface_type(self) -> InterfaceType:
        return InterfaceType.CHATGPT_APP

    def normalize_request(self, raw_request: dict[str, Any]) -> InterfaceRequest:
        return InterfaceRequest(
            interface=InterfaceType.CHATGPT_APP,
            user_prompt=raw_request.get("prompt", raw_request.get("user_prompt", "")),
            task_type=self._infer_task_type(raw_request),
            context=raw_request.get("context", {}),
            session_id=raw_request.get("session_id"),
            user_id=raw_request.get("user_id"),
            metadata=raw_request.get("metadata", {}),
        )

    def format_response(self, response: InterfaceResponse) -> dict[str, Any]:
        """Format for ChatGPT App: clean text with inline metrics."""
        status = "success" if response.success else "error"
        result = {
            "content": response.output,
            "status": status,
            "model": response.model.value,
            "usage": {
                "prompt_tokens": response.tokens_input,
                "completion_tokens": response.tokens_output,
            },
        }
        if not response.success:
            result["error"] = response.error
        return result

    def get_available_tools(self) -> list[str]:
        return ["web_search", "delegate_to_agent"]

    def get_max_context_tokens(self) -> int:
        return 128000  # GPT-4o context

    def _infer_task_type(self, raw: dict[str, Any]) -> TaskType | None:
        if "task_type" in raw:
            try:
                return TaskType(raw["task_type"])
            except ValueError:
                pass
        return None


class ClaudeCodeAdapter(InterfaceAdapter):
    """Adapter for Claude Code (Terminal) interface.

    Claude Code has:
    - Full file system access
    - Terminal/shell access
    - Git access
    - Test runner access
    - Most powerful for coding tasks
    """

    @property
    def interface_type(self) -> InterfaceType:
        return InterfaceType.CLAUDE_CODE

    def normalize_request(self, raw_request: dict[str, Any]) -> InterfaceRequest:
        return InterfaceRequest(
            interface=InterfaceType.CLAUDE_CODE,
            user_prompt=raw_request.get("prompt", raw_request.get("user_prompt", "")),
            task_type=self._infer_task_type(raw_request),
            context=raw_request.get("context", {}),
            files_involved=raw_request.get("files", raw_request.get("files_involved", [])),
            repo_url=raw_request.get("repo_url"),
            branch=raw_request.get("branch"),
            session_id=raw_request.get("session_id"),
            metadata=raw_request.get("metadata", {}),
        )

    def format_response(self, response: InterfaceResponse) -> dict[str, Any]:
        """Format for Claude Code: terminal-friendly output with metrics."""
        icon = "PASS" if response.success else "FAIL"
        parts = [f"[{icon}] {response.output}"]

        metrics = (
            f"  {response.latency_ms/1000:.1f}s | "
            f"${response.cost_usd:.3f} | "
            f"{response.tokens_input + response.tokens_output} tokens"
        )
        parts.append(metrics)

        if response.files_modified:
            parts.append(f"  Modified: {', '.join(response.files_modified)}")
        if response.tests_total > 0:
            parts.append(f"  Tests: {response.tests_passed}/{response.tests_total}")

        return {
            "output": "\n".join(parts),
            "success": response.success,
            "exit_code": 0 if response.success else 1,
        }

    def get_available_tools(self) -> list[str]:
        return [
            "read_file", "write_file", "list_directory", "search_files",
            "grep_content", "run_bash", "git_commit", "git_diff",
            "run_tests", "delegate_to_agent",
        ]

    def get_max_context_tokens(self) -> int:
        return 200000  # Claude Code has largest context

    def _infer_task_type(self, raw: dict[str, Any]) -> TaskType | None:
        if "task_type" in raw:
            try:
                return TaskType(raw["task_type"])
            except ValueError:
                pass
        return None


class CustomAPIAdapter(InterfaceAdapter):
    """Adapter for custom API integrations."""

    @property
    def interface_type(self) -> InterfaceType:
        return InterfaceType.CUSTOM_API

    def normalize_request(self, raw_request: dict[str, Any]) -> InterfaceRequest:
        return InterfaceRequest(
            interface=InterfaceType.CUSTOM_API,
            user_prompt=raw_request.get("prompt", raw_request.get("user_prompt", "")),
            task_type=None,
            context=raw_request.get("context", {}),
            files_involved=raw_request.get("files", []),
            metadata=raw_request.get("metadata", {}),
        )

    def format_response(self, response: InterfaceResponse) -> dict[str, Any]:
        return {
            "success": response.success,
            "output": response.output,
            "latency_ms": response.latency_ms,
            "tokens": {
                "input": response.tokens_input,
                "output": response.tokens_output,
            },
            "cost_usd": response.cost_usd,
        }


class CopilotAdapter(InterfaceAdapter):
    """Adapter for GitHub Copilot interface.

    Copilot has:
    - Inline code suggestions
    - Chat panel with file context
    - Limited file system access via workspace
    - No terminal access
    """

    @property
    def interface_type(self) -> InterfaceType:
        return InterfaceType.COPILOT

    def normalize_request(self, raw_request: dict[str, Any]) -> InterfaceRequest:
        return InterfaceRequest(
            interface=InterfaceType.COPILOT,
            user_prompt=raw_request.get("prompt", raw_request.get("user_prompt", "")),
            task_type=self._infer_task_type(raw_request),
            context=raw_request.get("context", {}),
            files_involved=raw_request.get("files", []),
            session_id=raw_request.get("session_id"),
            metadata=raw_request.get("metadata", {}),
        )

    def format_response(self, response: InterfaceResponse) -> dict[str, Any]:
        status = "success" if response.success else "error"
        result = {
            "content": response.output,
            "status": status,
            "model": response.model.value,
            "usage": {
                "prompt_tokens": response.tokens_input,
                "completion_tokens": response.tokens_output,
            },
        }
        if not response.success:
            result["error"] = response.error
        return result

    def get_available_tools(self) -> list[str]:
        return ["read_file", "search_files", "web_search"]

    def get_max_context_tokens(self) -> int:
        return 128000

    def _infer_task_type(self, raw: dict[str, Any]) -> TaskType | None:
        if "task_type" in raw:
            try:
                return TaskType(raw["task_type"])
            except ValueError:
                pass
        return None


class VSCodeAIAdapter(InterfaceAdapter):
    """Adapter for VS Code AI (GitHub Copilot Chat in VS Code) interface.

    VS Code AI has:
    - Chat panel with workspace context
    - File system access via workspace
    - Terminal access (via VS Code API)
    - Extension-based integration
    """

    @property
    def interface_type(self) -> InterfaceType:
        return InterfaceType.VSCODE_AI

    def normalize_request(self, raw_request: dict[str, Any]) -> InterfaceRequest:
        return InterfaceRequest(
            interface=InterfaceType.VSCODE_AI,
            user_prompt=raw_request.get("prompt", raw_request.get("user_prompt", "")),
            task_type=self._infer_task_type(raw_request),
            context=raw_request.get("context", {}),
            files_involved=raw_request.get("files", []),
            session_id=raw_request.get("session_id"),
            metadata=raw_request.get("metadata", {}),
        )

    def format_response(self, response: InterfaceResponse) -> dict[str, Any]:
        return {
            "content": response.output,
            "success": response.success,
            "notification": (
                f"SHARP: {'Passed' if response.success else 'Failed'} | "
                f"{response.latency_ms/1000:.1f}s | "
                f"${response.cost_usd:.3f}"
            ),
        }

    def get_available_tools(self) -> list[str]:
        return ["read_file", "write_file", "list_directory", "search_files"]

    def get_max_context_tokens(self) -> int:
        return 128000

    def _infer_task_type(self, raw: dict[str, Any]) -> TaskType | None:
        if "task_type" in raw:
            try:
                return TaskType(raw["task_type"])
            except ValueError:
                pass
        return None


class CursorAdapter(InterfaceAdapter):
    """Adapter for Cursor IDE interface.

    Cursor has:
    - Full file system access
    - Terminal access
    - Git access
    - AI chat + inline editing
    - Larger context window than most IDEs
    """

    @property
    def interface_type(self) -> InterfaceType:
        return InterfaceType.CURSOR

    def normalize_request(self, raw_request: dict[str, Any]) -> InterfaceRequest:
        return InterfaceRequest(
            interface=InterfaceType.CURSOR,
            user_prompt=raw_request.get("prompt", raw_request.get("user_prompt", "")),
            task_type=self._infer_task_type(raw_request),
            context=raw_request.get("context", {}),
            files_involved=raw_request.get("files", raw_request.get("files_involved", [])),
            repo_url=raw_request.get("repo_url"),
            branch=raw_request.get("branch"),
            session_id=raw_request.get("session_id"),
            metadata=raw_request.get("metadata", {}),
        )

    def format_response(self, response: InterfaceResponse) -> dict[str, Any]:
        icon = "PASS" if response.success else "FAIL"
        parts = [f"[{icon}] {response.output}"]

        metrics = (
            f"  {response.latency_ms/1000:.1f}s | "
            f"${response.cost_usd:.3f} | "
            f"{response.tokens_input + response.tokens_output} tokens"
        )
        parts.append(metrics)

        if response.files_modified:
            parts.append(f"  Modified: {', '.join(response.files_modified)}")
        if response.tests_total > 0:
            parts.append(f"  Tests: {response.tests_passed}/{response.tests_total}")

        return {
            "output": "\n".join(parts),
            "success": response.success,
            "exit_code": 0 if response.success else 1,
        }

    def get_available_tools(self) -> list[str]:
        return [
            "read_file", "write_file", "list_directory", "search_files",
            "grep_content", "run_bash", "git_commit", "git_diff",
        ]

    def get_max_context_tokens(self) -> int:
        return 200000

    def _infer_task_type(self, raw: dict[str, Any]) -> TaskType | None:
        if "task_type" in raw:
            try:
                return TaskType(raw["task_type"])
            except ValueError:
                pass
        return None


class WindsurfAdapter(InterfaceAdapter):
    """Adapter for Windsurf IDE interface.

    Windsurf has:
    - Full file system access
    - Terminal access
    - AI-powered code editing
    - Cascade (multi-step AI workflows)
    """

    @property
    def interface_type(self) -> InterfaceType:
        return InterfaceType.WINDSURF

    def normalize_request(self, raw_request: dict[str, Any]) -> InterfaceRequest:
        return InterfaceRequest(
            interface=InterfaceType.WINDSURF,
            user_prompt=raw_request.get("prompt", raw_request.get("user_prompt", "")),
            task_type=self._infer_task_type(raw_request),
            context=raw_request.get("context", {}),
            files_involved=raw_request.get("files", []),
            session_id=raw_request.get("session_id"),
            metadata=raw_request.get("metadata", {}),
        )

    def format_response(self, response: InterfaceResponse) -> dict[str, Any]:
        status = "success" if response.success else "error"
        return {
            "content": response.output,
            "status": status,
            "metrics": {
                "latency_ms": response.latency_ms,
                "cost_usd": response.cost_usd,
                "model": response.model.value,
            },
        }

    def get_available_tools(self) -> list[str]:
        return [
            "read_file", "write_file", "run_bash", "search_files",
        ]

    def get_max_context_tokens(self) -> int:
        return 128000

    def _infer_task_type(self, raw: dict[str, Any]) -> TaskType | None:
        if "task_type" in raw:
            try:
                return TaskType(raw["task_type"])
            except ValueError:
                pass
        return None


# ── Adapter Registry ───────────────────────────────────────────────────

ADAPTERS: dict[InterfaceType, type[InterfaceAdapter]] = {
    InterfaceType.CLAUDE_APP: ClaudeAppAdapter,
    InterfaceType.CHATGPT_APP: ChatGPTAppAdapter,
    InterfaceType.CLAUDE_CODE: ClaudeCodeAdapter,
    InterfaceType.CUSTOM_API: CustomAPIAdapter,
    InterfaceType.COPILOT: CopilotAdapter,
    InterfaceType.VSCODE_AI: VSCodeAIAdapter,
    InterfaceType.CURSOR: CursorAdapter,
    InterfaceType.WINDSURF: WindsurfAdapter,
}


def get_adapter(interface: InterfaceType) -> InterfaceAdapter:
    """Get an adapter instance for the given interface type."""
    adapter_cls = ADAPTERS.get(interface, CustomAPIAdapter)
    return adapter_cls()
