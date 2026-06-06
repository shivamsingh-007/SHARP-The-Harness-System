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
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


def create_app(config: HarnessConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI dashboard server."""
    app = FastAPI(title="SHARP Dashboard", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    engine = HarnessEngine(config or HarnessConfig.default())
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
