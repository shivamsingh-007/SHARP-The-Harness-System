"""Main HarnessEngine orchestrator - coordinates all zones."""

from __future__ import annotations

import inspect
import time
import uuid
from pathlib import Path
from typing import Any

from sharp.harness.core.config import HarnessConfig
from sharp.harness.core.errors import (
    BudgetExceededError,
    CircuitBreakerOpenError,
    RetryExhaustedError,
)
from sharp.harness.core.types import HarnessResult, ToolDefinition, ToolResult
from sharp.harness.context.curator import ContextCurator
from sharp.harness.prompt.composer import PromptComposer
from sharp.harness.execution.loop import ExecutionLoop, LoopResult, LoopState
from sharp.harness.execution.providers import LLMProvider
from sharp.harness.execution.tools import ToolRegistry
from sharp.harness.execution.subagents import SubAgentManager, SubAgentDefinition
from sharp.harness.execution.hooks import HookRegistry, HookEvent, HookContext
from sharp.harness.validation.validator import ResponseValidator
from sharp.harness.validation.retry import RetryEngine
from sharp.harness.safety.circuit_breaker import CircuitBreaker
from sharp.harness.safety.budget import BudgetManager
from sharp.harness.state.checkpoint import CheckpointManager
from sharp.harness.mcp.client import MCPClient
from sharp.harness.mcp.bridge import MCPToToolBridge
from sharp.harness.observability.logging import get_logger
from sharp.harness.observability.metrics import MetricsCollector

logger = get_logger(__name__)

# Keywords that indicate tool-calling tasks (should use REACT loop)
_TOOL_KEYWORDS = frozenset({
    "file", "directory", "list", "read", "write", "search", "grep",
    "calculate", "compute", "evaluate", "time", "date", "code",
    "function", "class", "import", "run", "execute", "script",
    "git", "commit", "push", "pull", "branch", "diff",
    "api", "http", "request", "response", "server", "database",
    "test", "lint", "build", "deploy", "docker", "container",
})


class HarnessEngine:
    """Main orchestrator that coordinates all harness zones.

    The engine manages the full lifecycle:
    1. Context Engineering: curate relevant context
    2. Prompt Engineering: assemble augmented prompt
    3. LLM Execution: run with tools/sub-agents (ReAct loop)
    4. Validation: check quality, retry if needed
    5. Safety: circuit breakers, budget controls
    6. State: checkpoint/resume
    7. Observability: trace, metric, log
    """

    def __init__(self, config: HarnessConfig | None = None) -> None:
        self.config = config or HarnessConfig.default()
        self._trace_id = str(uuid.uuid4())
        self._project_root: Path = Path.cwd()

        # Wire safety.blocked_commands → tool.blocked_tools
        if self.config.safety.blocked_commands and not self.config.tools.blocked_tools:
            self.config.tools.blocked_tools = list(self.config.safety.blocked_commands)

        # Initialize all zones
        self.context_curator = ContextCurator(self.config.context)
        self.prompt_composer = PromptComposer(self.config.prompt)
        self.tool_registry = ToolRegistry(self.config.tools)
        self.execution_loop = ExecutionLoop(self.config.execution, self.tool_registry)
        self.subagent_manager = SubAgentManager()
        self.validator = ResponseValidator(self.config.validation)
        self.retry_engine = RetryEngine(self.config.validation)
        self.circuit_breaker = CircuitBreaker(self.config.safety)
        self.budget_manager = BudgetManager(self.config.safety)
        self.checkpoint_manager = CheckpointManager(self.config.state)
        self.metrics = MetricsCollector(self.config.observability)
        self.hooks = HookRegistry()

        # MCP integration
        self.mcp_client = MCPClient(self.config.mcp)
        self.mcp_bridge = MCPToToolBridge(self.mcp_client, self.tool_registry)

        # State
        self._tools: list[ToolDefinition] = []
        self._memory: dict[str, str] = {}
        self._prior_outputs: list[str] = []
        self._mcp_connected = False
        self._last_loop_state: LoopState | None = None

        # Register built-in sub-agents
        self._register_default_subagents()

        # Register built-in tools
        self._register_builtin_tools()

    def _validate_path(self, path: str, must_exist: bool = False) -> Path | str:
        """Validate a path is within the project root.

        Args:
            path: Path string to validate.
            must_exist: If True, also check the path exists.

        Returns:
            Resolved Path if valid, or error string if invalid.
        """
        p = Path(path).resolve()
        if not p.is_relative_to(self._project_root.resolve()):
            return f"Error: Path '{path}' is outside project root"
        if must_exist and not p.exists():
            return f"Error: Path '{path}' not found"
        return p

    def _register_default_subagents(self) -> None:
        """Register default sub-agent definitions."""
        self.subagent_manager.register(SubAgentDefinition(
            name="researcher",
            role="Research Specialist",
            instructions="You are a research specialist. Find and synthesize information accurately.",
        ))
        self.subagent_manager.register(SubAgentDefinition(
            name="coder",
            role="Code Specialist",
            instructions="You are a code specialist. Write clean, correct, well-documented code.",
        ))
        self.subagent_manager.register(SubAgentDefinition(
            name="reviewer",
            role="Code Reviewer",
            instructions="You are a code reviewer. Review code for bugs, style issues, and improvements.",
        ))

    def _register_builtin_tools(self) -> None:
        """Register built-in tools for the ReAct loop."""
        from sharp.harness.core.types import RiskLevel

        async def get_current_time(timezone: str = "UTC") -> str:
            """Get the current date and time.

            Args:
                timezone: Timezone to return (UTC, local)
            """
            from datetime import datetime, timezone as tz
            now = datetime.now(tz.utc)
            return f"Current UTC time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}"

        async def calculate(expression: str) -> str:
            """Evaluate a mathematical expression safely.

            Args:
                expression: Math expression to evaluate (e.g., "2 + 2", "3 * 4")
            """
            import ast
            import operator
            allowed_ops = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.Pow: operator.pow,
                ast.USub: operator.neg,
            }
            def _eval(node: ast.AST) -> float:
                if isinstance(node, ast.Expression):
                    return _eval(node.body)
                elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                    return float(node.value)
                elif isinstance(node, ast.BinOp) and type(node.op) in allowed_ops:
                    left = _eval(node.left)
                    right = _eval(node.right)
                    return allowed_ops[type(node.op)](left, right)
                elif isinstance(node, ast.UnaryOp) and type(node.op) in allowed_ops:
                    return allowed_ops[type(node.op)](_eval(node.operand))
                raise ValueError(f"Unsupported expression: {ast.dump(node)}")
            tree = ast.parse(expression, mode="eval")
            result = _eval(tree)
            return f"{expression} = {result}"

        async def read_file(path: str) -> str:
            """Read the contents of a file.

            Args:
                path: Path to the file to read
            """
            p = self._validate_path(path, must_exist=True)
            if isinstance(p, str):
                return p
            if not p.is_file():
                return f"Error: '{path}' is not a file"
            try:
                content = p.read_text(encoding="utf-8")
                if len(content) > 5000:
                    content = content[:5000] + f"\n... [truncated, {len(p.read_text(encoding='utf-8'))} total chars]"
                return content
            except Exception as e:
                return f"Error reading file: {e}"

        async def list_directory(path: str = ".") -> str:
            """List files and directories in a path.

            Args:
                path: Directory path to list (default: current directory)
            """
            p = self._validate_path(path, must_exist=True)
            if isinstance(p, str):
                return p
            if not p.is_dir():
                return f"Error: '{path}' is not a directory"
            entries = []
            for entry in sorted(p.iterdir()):
                prefix = "  " if entry.is_file() else "d "
                size = entry.stat().st_size if entry.is_file() else 0
                entries.append(f"{prefix}{entry.name} ({size} bytes)" if entry.is_file() else f"{prefix}{entry.name}/")
            if not entries:
                return f"Directory '{path}' is empty"
            return "\n".join(entries[:50])  # Limit to 50 entries

        async def search_files(pattern: str, path: str = ".") -> str:
            """Search for files matching a glob pattern.

            Args:
                pattern: Glob pattern (e.g., "*.py", "**/*.js")
                path: Directory to search in (default: current directory)
            """
            p = self._validate_path(path, must_exist=True)
            if isinstance(p, str):
                return p
            matches = list(p.glob(pattern))
            if not matches:
                return f"No files found matching '{pattern}' in '{path}'"
            results = [str(m) for m in matches[:30]]  # Limit to 30 results
            return f"Found {len(matches)} files:\n" + "\n".join(results)

        async def grep_content(pattern: str, path: str = ".", include: str = "*") -> str:
            """Search file contents using regex pattern.

            Args:
                pattern: Regex pattern to search for
                path: Directory or file to search in (default: current directory)
                include: File pattern to include (default: all files)
            """
            import re
            p = self._validate_path(path, must_exist=True)
            if isinstance(p, str):
                return p
            compiled = re.compile(pattern, re.IGNORECASE)
            results = []
            files_searched = 0
            if p.is_file():
                files = [p]
            else:
                files = list(p.rglob(include))
            for f in files[:100]:  # Limit files searched
                files_searched += 1
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    for i, line in enumerate(content.split("\n"), 1):
                        if compiled.search(line):
                            results.append(f"{f}:{i}: {line.strip()[:100]}")
                            if len(results) >= 20:
                                break
                except Exception:
                    continue
                if len(results) >= 20:
                    break
            if not results:
                return f"No matches found for '{pattern}' in {files_searched} files"
            return f"Matches ({len(results)} found in {files_searched} files):\n" + "\n".join(results)

        self.tool(risk_level=RiskLevel.READ)(get_current_time)
        self.tool(risk_level=RiskLevel.READ)(calculate)
        self.tool(risk_level=RiskLevel.READ)(read_file)
        self.tool(risk_level=RiskLevel.READ)(list_directory)
        self.tool(risk_level=RiskLevel.READ)(search_files)
        self.tool(risk_level=RiskLevel.READ)(grep_content)

        async def delegate_to_agent(agent_name: str, task: str) -> str:
            """Delegate a task to a specialized sub-agent.

            Args:
                agent_name: Name of the sub-agent (researcher, coder, reviewer)
                task: The task for the sub-agent to perform
            """
            provider = LLMProvider(self.config.llm)
            result = await self.subagent_manager.spawn(
                name=agent_name,
                task=task,
                provider=provider,
            )
            if result.success:
                return f"Sub-agent '{agent_name}' completed: {result.output[:1000]}"
            else:
                return f"Sub-agent '{agent_name}' failed: {result.error}"

        self.tool(risk_level=RiskLevel.READ)(delegate_to_agent)
        logger.info(f"Registered {len(self._tools)} built-in tools")

    def tool(
        self,
        risk_level: Any = None,
        requires_approval: bool = False,
        timeout: float = 30.0,
    ) -> Any:
        """Decorator to register a tool."""
        from sharp.harness.core.types import RiskLevel

        level = risk_level or RiskLevel.READ

        def decorator(func: Any) -> Any:
            # Extract parameter schema from function signature
            parameters = self._extract_parameters(func)

            tool_def = ToolDefinition(
                name=func.__name__,
                description=func.__doc__ or f"Tool: {func.__name__}",
                parameters=parameters,
                risk_level=level,
                requires_approval=requires_approval,
                timeout=timeout,
            )
            self._tools.append(tool_def)
            self.tool_registry.register(func, tool_def)
            return func

        return decorator

    def _extract_parameters(self, func: Any) -> dict[str, Any]:
        """Extract JSON Schema parameters from a function's signature."""
        try:
            sig = inspect.signature(func)
        except (ValueError, TypeError):
            return {"type": "object", "properties": {}}

        properties = {}
        required = []

        for name, param in sig.parameters.items():
            prop: dict[str, Any] = {}

            # Map Python type hints to JSON Schema types
            if param.annotation != inspect.Parameter.empty:
                type_map = {
                    str: "string",
                    int: "integer",
                    float: "number",
                    bool: "boolean",
                    list: "array",
                    dict: "object",
                }
                prop["type"] = type_map.get(param.annotation, "string")

            # Set default value description
            if param.default != inspect.Parameter.empty:
                prop["default"] = param.default
            else:
                required.append(name)

            properties[name] = prop

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    @staticmethod
    def _is_simple_prompt(prompt: str) -> bool:
        """Detect if a prompt is simple enough to bypass the REACT loop.

        Simple prompts are short questions that don't need tool calling.
        """
        prompt_lower = prompt.lower().strip()
        # Short prompts without explicit tool-use keywords
        if len(prompt_lower) < 60:
            # Only trigger REACT for explicit tool-use phrases
            explicit_tool_phrases = [
                "use the", "call the", "run the", "execute the",
                "list the files", "read the file", "write to",
                "search for", "grep", "what time", "current time",
                "what date", "current date", "find the", "open the",
                "check the", "look at", "show me", "get the",
                "how many", "count the", "summarize", "list all",
            ]
            has_explicit_tool = any(phrase in prompt_lower for phrase in explicit_tool_phrases)
            if not has_explicit_tool:
                return True
        return False

    @staticmethod
    def _clean_output(output: str) -> str:
        """Clean up output from the execution loop.

        Strips JSON artifacts, LaTeX boxing, and other formatting issues.
        """
        if not output:
            return output

        import re

        # Strip JSON array wrapper: [{"name": "Final Answer", "text": "..."}] -> ...
        json_array_match = re.match(r'^\s*\[\s*\{.*?"text"\s*:\s*"(.+?)"\s*\}\s*\]\s*$', output, re.DOTALL)
        if json_array_match:
            output = json_array_match.group(1)

        # Strip LaTeX boxing: $\boxed{4}$ -> 4
        box_match = re.search(r'\\boxed\{(.+?)\}', output)
        if box_match:
            output = box_match.group(1).strip()

        # Strip leading/trailing whitespace
        output = output.strip()

        return output

    def add_memory(self, key: str, value: str) -> None:
        """Add an item to persistent memory."""
        self._memory[key] = value

    def load_memory_file(self, path: str) -> None:
        """Load memory from a file (like CLAUDE.md)."""
        p = self._validate_path(path, must_exist=True)
        if isinstance(p, str):
            logger.warning(f"Memory file rejected: {p}")
            return
        content = p.read_text(encoding="utf-8")
        self._memory[path] = content

    async def connect_mcp_servers(self) -> None:
        """Connect to all configured MCP servers and discover their capabilities."""
        if not self.config.mcp.enabled:
            return

        if self._mcp_connected:
            logger.warning("MCP servers already connected")
            return

        logger.info("Connecting to MCP servers...")

        for server_config in self.config.mcp.servers:
            if not server_config.enabled:
                logger.debug(f"Skipping disabled MCP server: {server_config.name}")
                continue

            try:
                await self.mcp_client.connect_from_config(server_config)
            except Exception as e:
                logger.warning(f"MCP server '{server_config.name}' connection failed (non-fatal): {e}")
                continue

        # Bridge tools into ToolRegistry
        registered_tools = await self.mcp_bridge.register_all_tools()
        self._tools.extend(registered_tools)

        # Apply risk overrides
        if self.config.mcp.tool_risk_overrides:
            await self.mcp_bridge.apply_risk_overrides(self.config.mcp.tool_risk_overrides)

        # Feed MCP resources into context
        mcp_resources = self.mcp_bridge.get_context_from_resources()
        if mcp_resources:
            for source in mcp_resources:
                self.context_curator.source_manager.add(source)

        self._mcp_connected = True
        logger.info(
            f"MCP connected: {len(self.mcp_client.connected_servers)} servers, "
            f"{len(registered_tools)} tools registered"
        )

    async def close(self) -> None:
        """Clean up MCP connections and resources."""
        if self._mcp_connected:
            await self.mcp_client.disconnect_all()
            self._mcp_connected = False
            logger.info("MCP connections closed")

    async def __aenter__(self) -> "HarnessEngine":
        """Async context manager entry."""
        if self.config.mcp.enabled and self.config.mcp.auto_discover:
            await self.connect_mcp_servers()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def run(self, user_request: str, **kwargs: Any) -> HarnessResult:
        """Execute the full harness pipeline.

        Args:
            user_request: The user's request/prompt.
            **kwargs: Additional context sources.

        Returns:
            HarnessResult with the final output and metadata.
        """
        start_time = time.time()
        self._trace_id = str(uuid.uuid4())
        self.metrics.start_trace(self._trace_id)

        try:
            # Pre-flight checks
            self.circuit_breaker.check()
            self.budget_manager.check()

            # Auto-connect MCP servers if configured
            if self.config.mcp.enabled and self.config.mcp.auto_discover and not self._mcp_connected:
                await self.connect_mcp_servers()

            # Fire session_start hook
            session_ctx = await self.hooks.fire(HookEvent.SESSION_START, HookContext(
                event=HookEvent.SESSION_START,
                data={"user_request": user_request, "trace_id": self._trace_id},
            ))
            if session_ctx.cancel:
                logger.info("Session cancelled by session_start hook")
                return HarnessResult(
                    success=False,
                    output="",
                    total_latency_ms=(time.time() - start_time) * 1000,
                    error="Session cancelled by hook",
                    trace_id=self._trace_id,
                )

            # Load checkpoint if available
            checkpoint = self.checkpoint_manager.load(self._trace_id)

            # Phase 1: Context Engineering
            logger.info("Phase 1: Context Engineering")
            curated = self.context_curator.curate(
                user_request=user_request,
                memory=self._memory,
                prior_outputs=self._prior_outputs,
                retrieved_docs=kwargs.get("docs", []),
                checkpoint_context=None,
            )

            # Phase 2: Prompt Engineering
            logger.info("Phase 2: Prompt Engineering")
            augmented_prompt = self.prompt_composer.compose(
                user_request=user_request,
                context_sources=curated.sources,
                tools=self._tools,
            )

            # Phase 3-4: Execution + Validation with retry
            logger.info("Phase 3-4: Execution + Validation")
            result = await self._execute_with_retry(
                augmented_prompt=augmented_prompt,
                user_request=user_request,
            )

            # Post-flight
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.end_trace(
                self._trace_id,
                success=True,
                latency_ms=elapsed_ms,
                tokens=result.total_tokens,
                cost=result.total_cost_usd,
            )
            self.circuit_breaker.record_success()
            self.budget_manager.record_tokens(result.total_tokens)
            self.budget_manager.record_cost(result.total_cost_usd)

            # Save checkpoint
            self.checkpoint_manager.save(
                self._trace_id,
                context=curated.sources,
                output=result.output,
            )

            # Store output for future context
            self._prior_outputs.append(result.output)

            # Fire session_end hook
            await self.hooks.fire(HookEvent.SESSION_END, HookContext(
                event=HookEvent.SESSION_END,
                data={
                    "trace_id": self._trace_id,
                    "output": result.output,
                    "success": True,
                    "attempts": result.attempts,
                },
            ))

            return HarnessResult(
                success=True,
                output=result.output,
                attempts=result.attempts,
                total_latency_ms=elapsed_ms,
                total_cost_usd=result.total_cost_usd,
                total_tokens=result.total_tokens,
                validation_score=result.validation_score,
                trace_id=self._trace_id,
            )

        except (CircuitBreakerOpenError, BudgetExceededError) as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.end_trace(self._trace_id, success=False, latency_ms=elapsed_ms)
            await self.hooks.fire(HookEvent.SESSION_END, HookContext(
                event=HookEvent.SESSION_END,
                data={"trace_id": self._trace_id, "success": False, "error": str(e)},
            ))
            return HarnessResult(
                success=False,
                output="",
                total_latency_ms=elapsed_ms,
                error=str(e),
                trace_id=self._trace_id,
            )

        except RetryExhaustedError as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.end_trace(self._trace_id, success=False, latency_ms=elapsed_ms)
            self.circuit_breaker.record_failure()
            await self.hooks.fire(HookEvent.SESSION_END, HookContext(
                event=HookEvent.SESSION_END,
                data={"trace_id": self._trace_id, "success": False, "error": str(e)},
            ))
            return HarnessResult(
                success=False,
                output="",
                total_latency_ms=elapsed_ms,
                error=str(e),
                trace_id=self._trace_id,
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.end_trace(self._trace_id, success=False, latency_ms=elapsed_ms)
            self.circuit_breaker.record_failure()
            logger.exception("Harness execution failed")
            await self.hooks.fire(HookEvent.SESSION_END, HookContext(
                event=HookEvent.SESSION_END,
                data={"trace_id": self._trace_id, "success": False, "error": str(e)},
            ))
            return HarnessResult(
                success=False,
                output="",
                total_latency_ms=elapsed_ms,
                error=str(e),
                trace_id=self._trace_id,
            )

    async def _execute_with_retry(
        self,
        augmented_prompt: Any,
        user_request: str,
    ) -> Any:
        """Execute LLM with validation retry loop.

        Uses the ExecutionLoop for ReAct-style execution when tools are available,
        falls back to direct LLM call for simple requests.
        """
        max_attempts = self.config.validation.max_retries + 1
        last_error = ""

        for attempt in range(1, max_attempts + 1):
            logger.info(f"Attempt {attempt}/{max_attempts}")

            provider = LLMProvider(self.config.llm)

            # Fire before_execute hook
            before_ctx = await self.hooks.fire(HookEvent.BEFORE_EXECUTE, HookContext(
                event=HookEvent.BEFORE_EXECUTE,
                data={"attempt": attempt, "user_request": user_request},
            ))
            if before_ctx.cancel:
                logger.info("Execution cancelled by before_execute hook")
                break

            # Fast path: simple prompts bypass the REACT loop
            is_simple = self._is_simple_prompt(user_request)
            has_tools = bool(self._tools) and self.config.prompt.include_tools_in_prompt
            loop_policy = self.config.execution.loop_policy
            if loop_policy == "always_react":
                use_loop = has_tools and self.config.execution.loop_strategy.value == "react"
            elif loop_policy == "never_react":
                use_loop = False
            else:  # auto
                use_loop = has_tools and self.config.execution.loop_strategy.value == "react" and not is_simple

            if use_loop:
                # Run through the ReAct execution loop
                loop_result = await self.execution_loop.run(
                    provider=provider,
                    user_request=augmented_prompt.user_message,
                    tools=self._tools,
                    system_prompt=augmented_prompt.system_prompt,
                )
                output = loop_result.output
                # Preserve loop state for dashboard
                self._last_loop_state = LoopState(
                    iteration=self.execution_loop.state.iteration,
                    history=list(self.execution_loop.state.history),
                    tool_calls=list(self.execution_loop.state.tool_calls),
                    observations=list(self.execution_loop.state.observations),
                    done=self.execution_loop.state.done,
                    final_answer=self.execution_loop.state.final_answer,
                )
                # Use real metadata from loop result
                tokens_used = loop_result.total_tokens
                cost = loop_result.total_cost_usd
            else:
                # Direct LLM call (no tools or non-react strategy or simple prompt)
                # For simple prompts, use a minimal system prompt without tool references
                system = augmented_prompt.system_prompt
                if is_simple:
                    system = "You are a helpful assistant. Answer the question directly and concisely. Do not mention tools."

                response = await provider.complete(
                    system_prompt=system,
                    user_message=augmented_prompt.user_message,
                    tools=self._tools if has_tools and not is_simple else [],
                )
                output = response.content
                tokens_used = response.tokens_used
                cost = response.cost_usd

            # Post-process output: strip JSON artifacts from loop observations
            output = self._clean_output(output)

            # Validate
            validation = await self.validator.validate(
                response=output,
                user_request=user_request,
                context=augmented_prompt.context_summary,
            )

            if validation.passed:
                # Fire after_execute hook
                await self.hooks.fire(HookEvent.AFTER_EXECUTE, HookContext(
                    event=HookEvent.AFTER_EXECUTE,
                    data={
                        "attempt": attempt,
                        "output": output,
                        "validation_score": validation.score,
                    },
                ))

                return _ExecutionResult(
                    output=output,
                    attempts=attempt,
                    total_cost_usd=cost,
                    total_tokens=tokens_used,
                    validation_score=validation.score,
                )

            # Record failure for retry mutation
            last_error = "; ".join(validation.issues)
            logger.debug(f"Validation failed (attempt {attempt}): {last_error}")

            # Fire on_validation_failure hook
            await self.hooks.fire(HookEvent.ON_VALIDATION_FAILURE, HookContext(
                event=HookEvent.ON_VALIDATION_FAILURE,
                data={
                    "attempt": attempt,
                    "issues": validation.issues,
                    "score": validation.score,
                    "output": output,
                },
            ))

            # Check if we should retry
            if attempt < max_attempts:
                # Fire on_retry hook
                await self.hooks.fire(HookEvent.ON_RETRY, HookContext(
                    event=HookEvent.ON_RETRY,
                    data={
                        "attempt": attempt,
                        "validation_result": validation,
                    },
                ))

                mutated = self.retry_engine.mutate_for_retry(
                    original_prompt=augmented_prompt,
                    validation_result=validation,
                    attempt=attempt,
                )
                augmented_prompt = mutated

        raise RetryExhaustedError(max_attempts, last_error)

    async def delegate_to_subagent(
        self,
        agent_name: str,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Delegate a task to a sub-agent.

        Args:
            agent_name: Name of the registered sub-agent.
            task: The task to delegate.
            context: Additional context for the sub-agent.

        Returns:
            The sub-agent's response.
        """
        provider = LLMProvider(self.config.llm)
        result = await self.subagent_manager.spawn(
            name=agent_name,
            task=task,
            provider=provider,
            context=context,
        )
        return result.output


class _ExecutionResult:
    """Internal result from execution with retry."""

    def __init__(
        self,
        output: str,
        attempts: int,
        total_cost_usd: float,
        total_tokens: int,
        validation_score: float,
    ) -> None:
        self.output = output
        self.attempts = attempts
        self.total_cost_usd = total_cost_usd
        self.total_tokens = total_tokens
        self.validation_score = validation_score
