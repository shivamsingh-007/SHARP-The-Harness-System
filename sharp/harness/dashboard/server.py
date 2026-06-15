"""FastAPI server for SHARP dashboard."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from sharp.harness.core.engine import HarnessEngine
from sharp.harness.core.config import HarnessConfig
from sharp.harness.dashboard.bridge import DashboardBridge
from sharp.harness.orchestration.router import IntentRouter, IntentRouterConfig
from sharp.harness.orchestration.orchestrator import Orchestrator, OrchestratorConfig
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)

# Global engine registry for sharing between opencode and dashboard
_global_engines: dict[str, HarnessEngine] = {}


def register_engine(name: str, engine: HarnessEngine) -> None:
    """Register a global engine instance for dashboard access."""
    _global_engines[name] = engine
    logger.info(f"Registered global engine: {name}")


def get_engine(name: str = "default") -> HarnessEngine | None:
    """Get a registered global engine instance."""
    return _global_engines.get(name)


def create_app(config: HarnessConfig | None = None, engine: HarnessEngine | None = None) -> FastAPI:
    """Create and configure the FastAPI dashboard server.

    Args:
        config: Harness configuration (used if engine not provided)
        engine: Shared engine instance (for connecting to opencode session)
    """
    app = FastAPI(title="SHARP Dashboard", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Use provided engine, global engine, or create new one
    if engine is None:
        engine = get_engine() or HarnessEngine(config or HarnessConfig.default())
        if engine not in _global_engines.values():
            register_engine("default", engine)
    bridge = DashboardBridge(engine)
    ws_clients: set[WebSocket] = set()
    _startup_time = time.time()

    async def broadcast(message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in ws_clients:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            ws_clients.discard(ws)

    @app.get("/api/health")
    async def health():
        h = bridge.get_health()
        h.uptime_seconds = time.time() - _startup_time
        return h

    @app.get("/api/metrics/aggregate")
    async def metrics_aggregate():
        return bridge.get_metrics_aggregate()

    @app.get("/api/metrics/traces")
    async def metrics_traces():
        return bridge.get_metrics_traces()

    @app.get("/api/metrics/timeseries")
    async def metrics_timeseries(window: int = 60):
        return bridge.get_metrics_timeseries(window)

    @app.get("/api/connections")
    async def connections():
        return bridge.get_connections()

    @app.get("/api/execution/current")
    async def execution_current():
        return bridge.get_execution_current()

    @app.get("/api/safety")
    async def safety():
        return bridge.get_safety()

    # ─── MCP Server Management ────────────────────────────────────────

    @app.get("/api/mcp/servers")
    async def mcp_servers():
        servers = []
        for name in engine.mcp_client.registry._servers.values():
            servers.append({
                "name": name.name,
                "transport": name.transport,
                "command": name.command,
                "args": name.args,
                "url": name.url,
                "enabled": name.enabled,
                "description": name.description,
                "connected": name.name in engine.mcp_client._connected,
            })
        connected = engine.mcp_client.connected_servers
        return {
            "servers": servers,
            "connected": connected,
            "tools": list(engine.mcp_client.discovered_tools.keys()),
            "resources": list(engine.mcp_client.discovered_resources.keys()),
            "prompts": list(engine.mcp_client.discovered_prompts.keys()),
        }

    @app.post("/api/mcp/servers")
    async def mcp_add_server(server: dict[str, Any]):
        from sharp.harness.mcp.registry import MCPServer
        name = server.get("name", "")
        if not name:
            return {"error": "Server name required"}
        mcp_server = MCPServer(
            name=name,
            transport=server.get("transport", "stdio"),
            command=server.get("command"),
            args=server.get("args", []),
            url=server.get("url"),
            enabled=server.get("enabled", True),
            description=server.get("description", ""),
        )
        engine.mcp_client.registry.register(mcp_server)
        return {"ok": True, "server": name}

    @app.delete("/api/mcp/servers/{name}")
    async def mcp_remove_server(name: str):
        removed = engine.mcp_client.registry.unregister(name)
        return {"ok": removed, "server": name}

    @app.post("/api/mcp/servers/{name}/connect")
    async def mcp_connect_server(name: str):
        server = engine.mcp_client.registry.get(name)
        if not server:
            return {"error": f"Server '{name}' not found"}
        try:
            if server.transport == "stdio" and server.command:
                await engine.mcp_client.connect_stdio(
                    name, server.command, server.args
                )
            elif server.transport == "http" and server.url:
                await engine.mcp_client.connect_http(name, server.url)
            else:
                return {"error": "Invalid transport or missing config"}
            return {"ok": True, "server": name, "connected": True}
        except Exception as e:
            return {"error": str(e), "server": name}

    @app.post("/api/mcp/servers/{name}/disconnect")
    async def mcp_disconnect_server(name: str):
        if name in engine.mcp_client._sessions:
            try:
                session = engine.mcp_client._sessions[name]
                await session.__aexit__(None, None, None)
                del engine.mcp_client._sessions[name]
                engine.mcp_client._connected.discard(name)
                return {"ok": True, "server": name}
            except Exception as e:
                return {"error": str(e)}
        return {"error": f"Server '{name}' not connected"}

    # ─── Plugin Management ────────────────────────────────────────────

    @app.get("/api/plugins")
    async def plugins():
        mcp_tools = engine.mcp_client.discovered_tools
        registered_tools = engine._tools
        builtin_tools = [
            {"name": t.name, "description": t.description, "risk_level": t.risk_level.value, "source": "builtin"}
            for t in registered_tools
        ]
        mcp_tool_list = [
            {"name": name, "description": info.get("description", ""), "risk_level": "read", "source": "mcp", "server": info.get("server", "")}
            for name, info in mcp_tools.items()
        ]
        return {
            "builtin": builtin_tools,
            "mcp": mcp_tool_list,
            "total": len(builtin_tools) + len(mcp_tool_list),
        }

    @app.get("/api/config")
    async def config():
        return {
            "llm": {
                "provider": engine.config.llm.provider,
                "model": engine.config.llm.model,
                "temperature": engine.config.llm.temperature,
                "max_tokens": engine.config.llm.max_tokens,
            },
            "execution": {
                "loop_strategy": engine.config.execution.loop_strategy,
                "max_iterations": engine.config.execution.max_iterations,
            },
            "validation": {
                "enabled": engine.config.validation.enabled,
                "level": engine.config.validation.level,
                "llm_judge_enabled": engine.config.validation.llm_judge_enabled,
                "max_retries": engine.config.validation.max_retries,
            },
            "safety": {
                "circuit_breaker_enabled": engine.config.safety.circuit_breaker_enabled,
                "budget_enabled": engine.config.safety.budget_enabled,
            },
            "mcp": {
                "enabled": engine.config.mcp.enabled,
                "auto_discover": engine.config.mcp.auto_discover,
            },
        }

    @app.get("/api/sessions")
    async def sessions():
        """Show all active sessions (engines)."""
        sessions_list = []
        for name, eng in _global_engines.items():
            agg = eng.metrics.get_aggregate()
            sessions_list.append({
                "name": name,
                "trace_id": eng._trace_id,
                "total_traces": agg["total_traces"],
                "total_tokens": agg["total_tokens"],
                "total_cost": agg["total_cost"],
                "tools_registered": len(eng._tools),
                "mcp_connected": eng._mcp_connected,
            })
        return {"sessions": sessions_list, "active": len(sessions_list)}

    @app.post("/api/engine/register")
    async def engine_register(data: dict[str, str]):
        """Register an external engine instance (e.g., from opencode session)."""
        name = data.get("name", "default")
        # The engine must be passed via the app's engine reference
        register_engine(name, engine)
        return {"ok": True, "name": name, "registered": True}

    @app.post("/api/engine/run")
    async def engine_run(request: dict[str, str]):
        user_request = request.get("request", "")
        if not user_request:
            return {"error": "No request provided"}

        try:
            bridge.record_run()
            result = await engine.run(user_request)
            await broadcast({
                "type": "execution_complete",
                "data": {
                    "success": result.success,
                    "output": result.output[:500],
                    "latency_ms": result.total_latency_ms,
                    "tokens": result.total_tokens,
                    "cost": result.total_cost_usd,
                },
            })
            return {
                "success": result.success,
                "output": result.output,
                "latency_ms": result.total_latency_ms,
                "tokens": result.total_tokens,
                "cost": result.total_cost_usd,
                "attempts": result.attempts,
            }
        except Exception as e:
            bridge.record_error(str(e))
            return {"error": str(e)}

    # ─── Orchestration API ──────────────────────────────────────────────

    @app.post("/api/route")
    async def route_task(request: dict[str, Any]):
        """Route a task to the best AI interface/model.

        Input: {"task": "fix the login bug", "context": {"files_involved": [...]}}
        Output: {"decision": {...}, "explanation": "..."}
        """
        task = request.get("task", "")
        if not task:
            return {"error": "No task provided"}

        context = request.get("context", {})
        router = IntentRouter()
        decision = router.route(task, context)

        return {
            "decision": {
                "task_type": decision.task_type.value,
                "complexity": decision.complexity.value,
                "recommended_interface": decision.recommended_interface.value,
                "recommended_model": decision.recommended_model.value,
                "estimated_latency_ms": decision.estimated_latency_ms,
                "estimated_cost_usd": decision.estimated_cost_usd,
                "confidence": decision.confidence,
            },
            "explanation": decision.reasoning,
            "alternatives": {
                "interfaces": [i.value for i in decision.alternative_interfaces],
                "models": [m.value for m in decision.alternative_models],
            },
        }

    @app.post("/api/validate")
    async def validate_output(request: dict[str, Any]):
        """Validate AI output for hallucinations and quality.

        Input: {"output": "...", "task_type": "rag|coding"}
        Output: {"passed": bool, "score": float, "issues": [...]}
        """
        output = request.get("output", "")
        if not output:
            return {"error": "No output provided"}

        task_type = request.get("task_type", "general")

        try:
            import os
            if os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OPENAI_API_KEY"):
                val_config = HarnessConfig.default()
            else:
                val_config = HarnessConfig.ollama()
            val_engine = HarnessEngine(val_config)
            result = await val_engine.validator.validate(
                response=output,
                user_request=f"Validate {task_type} output",
                context=f"Task type: {task_type}",
            )
            return {
                "passed": result.passed,
                "score": result.score,
                "issues": result.issues if hasattr(result, "issues") else [],
                "details": result.details if hasattr(result, "details") else {},
            }
        except Exception as e:
            return {"error": str(e), "passed": False, "score": 0.0, "issues": [str(e)]}

    @app.post("/api/coding/session")
    async def coding_session(request: dict[str, Any]):
        """Run a coding agent session (start + DPEVR loop + end).

        Input: {"project_root": "/path/to/project", "session_id": 1, "engine_config": {...}}
        Output: {"status": "...", "result": {...}, "feature": {...}, "progress": [...]}
        """
        project_root = request.get("project_root", ".")
        session_id = request.get("session_id", 1)
        engine_config = request.get("engine_config", None)

        try:
            from sharp.harness.agents.coding import CodingAgent, CodingConfig

            config = CodingConfig(project_root=project_root, engine_config=engine_config)
            agent = CodingAgent(config=config)

            # Step 1: Start session
            state = await agent.start_session()

            # Step 2: Run DPEVR on next feature
            if state.next_feature:
                dpevr_result = await agent.run_dpevr(state.next_feature)

                # Step 3: End session (git commit + progress update)
                await agent.end_session(
                    feature=state.next_feature,
                    result=dpevr_result,
                )

                return {
                    "status": "completed",
                    "session_id": session_id,
                    "result": {
                        "success": dpevr_result.success,
                        "feature_id": dpevr_result.feature_id,
                        "attempts": dpevr_result.attempts,
                        "tests_passed": dpevr_result.tests_passed,
                        "duration_ms": dpevr_result.total_duration_ms,
                    },
                    "feature": {
                        "id": state.next_feature.id,
                        "description": state.next_feature.description,
                    },
                    "project_root": project_root,
                }
            else:
                return {
                    "status": "no_features",
                    "session_id": session_id,
                    "message": "All features completed",
                    "project_root": project_root,
                }
        except Exception as e:
            return {"error": str(e), "status": "failed"}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        ws_clients.add(websocket)
        logger.info(f"Dashboard client connected ({len(ws_clients)} total)")

        try:
            while True:
                try:
                    msg = await asyncio.wait_for(websocket.receive_text(), timeout=2.0)
                    data = json.loads(msg)
                    if data.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except asyncio.TimeoutError:
                    pass

                try:
                    health = bridge.get_health()
                    metrics = bridge.get_metrics_aggregate()
                    execution = bridge.get_execution_current()
                    safety = bridge.get_safety()

                    await websocket.send_json({
                        "type": "snapshot",
                        "data": {
                            "health": health.model_dump(),
                            "metrics": metrics.model_dump(),
                            "execution": execution.model_dump(),
                            "safety": safety.model_dump(),
                            "timestamp": time.time(),
                        },
                    })
                except Exception:
                    pass

                await asyncio.sleep(2)

        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            ws_clients.discard(websocket)
            logger.info(f"Dashboard client disconnected ({len(ws_clients)} total)")

    app.engine = engine  # type: ignore
    app.bridge = bridge  # type: ignore

    return app


app = create_app()
