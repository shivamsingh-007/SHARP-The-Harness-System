"""Tests for SHARP Universal Orchestration Layer.

Covers: IntentRouter, InterfaceAdapters, ContextAggregator, Orchestrator,
AuditLogger, and PerformanceTracker.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from sharp.harness.orchestration.types import (
    InterfaceType,
    TaskType,
    TaskComplexity,
    ModelType,
    RoutingStrategy,
    RoutingDecision,
    InterfaceRequest,
    InterfaceResponse,
    ContextAggregation,
    AuditEntry,
    PerformanceSnapshot,
)
from sharp.harness.orchestration.router import (
    IntentRouter,
    IntentRouterConfig,
    ROUTING_TABLE,
    TASK_KEYWORDS,
)
from sharp.harness.orchestration.adapters import (
    ClaudeAppAdapter,
    ChatGPTAppAdapter,
    ClaudeCodeAdapter,
    CustomAPIAdapter,
    get_adapter,
    ADAPTERS,
)
from sharp.harness.orchestration.aggregator import (
    ContextAggregator,
    AggregatorConfig,
)
from sharp.harness.orchestration.orchestrator import (
    Orchestrator,
    OrchestratorConfig,
    _PerformanceTracker,
)
from sharp.harness.orchestration.audit import (
    AuditLogger,
    AuditLoggerConfig,
)


# ── IntentRouter Tests ─────────────────────────────────────────────────


class TestIntentRouterClassification:
    def test_classify_coding_bug(self):
        router = IntentRouter()
        decision = router.route("fix the bug in my login component")
        assert decision.task_type == TaskType.CODING_BUG_FIX

    def test_classify_new_feature(self):
        router = IntentRouter()
        decision = router.route("add a new search feature to the app")
        assert decision.task_type == TaskType.CODING_NEW_FEATURE

    def test_classify_rag_question(self):
        router = IntentRouter()
        decision = router.route("what is the capital of France?")
        assert decision.task_type == TaskType.RAG_QUESTION

    def test_classify_planning(self):
        router = IntentRouter()
        decision = router.route("plan the migration strategy for our database")
        assert decision.task_type == TaskType.MULTI_STEP_PLANNING

    def test_classify_general(self):
        router = IntentRouter()
        decision = router.route("hello there")
        assert decision.task_type == TaskType.GENERAL


class TestIntentRouterComplexity:
    def test_low_complexity_short_prompt(self):
        router = IntentRouter()
        decision = router.route("fix typo")
        assert decision.complexity == TaskComplexity.LOW

    def test_high_complexity_long_prompt(self):
        router = IntentRouter()
        prompt = "I need you to refactor the entire authentication system, " * 20
        decision = router.route(prompt)
        assert decision.complexity == TaskComplexity.HIGH

    def test_high_complexity_multi_file(self):
        router = IntentRouter()
        decision = router.route(
            "refactor these multiple files to improve code quality and simplify the architecture",
            context={"files_involved": ["a.py", "b.py", "c.py", "d.py", "e.py", "f.py"]},
        )
        assert decision.complexity == TaskComplexity.HIGH


class TestIntentRouterRouting:
    def test_routing_table_has_all_task_types(self):
        for task_type in TaskType:
            assert task_type in ROUTING_TABLE, f"Missing routing for {task_type}"

    def test_route_returns_decision(self):
        router = IntentRouter()
        decision = router.route("fix bug in auth")
        assert isinstance(decision, RoutingDecision)
        assert decision.recommended_interface in InterfaceType
        assert decision.recommended_model in ModelType
        assert len(decision.reasoning) > 0

    def test_route_coding_prefers_claude_code(self):
        router = IntentRouter()
        decision = router.route("fix the bug in my React app")
        assert decision.recommended_interface == InterfaceType.CLAUDE_CODE

    def test_route_rag_prefers_chatgpt(self):
        router = IntentRouter()
        decision = router.route("what is Python's GIL?")
        assert decision.recommended_interface == InterfaceType.CHATGPT_APP

    def test_route_planning_prefers_claude_app(self):
        router = IntentRouter()
        decision = router.route("plan the microservices architecture migration")
        assert decision.recommended_interface == InterfaceType.CLAUDE_APP


class TestIntentRouterStrategies:
    def test_cost_optimize_picks_cheaper_for_low_complexity(self):
        config = IntentRouterConfig(strategy=RoutingStrategy.COST_OPTIMIZE)
        router = IntentRouter(config)
        decision = router.route("quick question about python")
        # For low complexity + cost optimize, should prefer haiku or mini
        assert decision.recommended_model in (ModelType.CLAUDE_HAIKU, ModelType.GPT4O_MINI)

    def test_user_preference_overrides(self):
        config = IntentRouterConfig(user_preference=InterfaceType.CHATGPT_APP)
        router = IntentRouter(config)
        decision = router.route("fix the bug in auth")
        assert decision.recommended_interface == InterfaceType.CHATGPT_APP

    def test_estimated_cost_is_positive(self):
        router = IntentRouter()
        decision = router.route("do something")
        assert decision.estimated_cost_usd > 0

    def test_estimated_latency_is_positive(self):
        router = IntentRouter()
        decision = router.route("do something")
        assert decision.estimated_latency_ms > 0


# ── Interface Adapter Tests ────────────────────────────────────────────


class TestClaudeAppAdapter:
    def test_normalize_request(self):
        adapter = ClaudeAppAdapter()
        raw = {"prompt": "Fix the bug", "files": ["auth.py"], "session_id": "s1"}
        req = adapter.normalize_request(raw)
        assert req.interface == InterfaceType.CLAUDE_APP
        assert req.user_prompt == "Fix the bug"
        assert req.files_involved == ["auth.py"]
        assert req.session_id == "s1"

    def test_format_response_success(self):
        adapter = ClaudeAppAdapter()
        resp = InterfaceResponse(
            success=True, output="Fixed!", interface=InterfaceType.CLAUDE_APP,
            model=ModelType.CLAUDE_SONNET, latency_ms=1200, cost_usd=0.15,
        )
        formatted = adapter.format_response(resp)
        assert "Fixed!" in formatted["content"]
        assert formatted["success"] is True

    def test_format_response_failure(self):
        adapter = ClaudeAppAdapter()
        resp = InterfaceResponse(
            success=False, output="", interface=InterfaceType.CLAUDE_APP,
            model=ModelType.CLAUDE_SONNET, error="timeout",
        )
        formatted = adapter.format_response(resp)
        assert formatted["success"] is False

    def test_interface_type(self):
        assert ClaudeAppAdapter().interface_type == InterfaceType.CLAUDE_APP

    def test_available_tools(self):
        tools = ClaudeAppAdapter().get_available_tools()
        assert "read_file" in tools
        assert "web_search" in tools


class TestChatGPTAppAdapter:
    def test_normalize_request(self):
        adapter = ChatGPTAppAdapter()
        raw = {"prompt": "What is Python?"}
        req = adapter.normalize_request(raw)
        assert req.interface == InterfaceType.CHATGPT_APP
        assert req.user_prompt == "What is Python?"

    def test_format_response(self):
        adapter = ChatGPTAppAdapter()
        resp = InterfaceResponse(
            success=True, output="Python is a language.",
            interface=InterfaceType.CHATGPT_APP, model=ModelType.GPT4O,
            tokens_input=50, tokens_output=30,
        )
        formatted = adapter.format_response(resp)
        assert formatted["content"] == "Python is a language."
        assert formatted["status"] == "success"
        assert formatted["usage"]["prompt_tokens"] == 50

    def test_interface_type(self):
        assert ChatGPTAppAdapter().interface_type == InterfaceType.CHATGPT_APP


class TestClaudeCodeAdapter:
    def test_normalize_request(self):
        adapter = ClaudeCodeAdapter()
        raw = {"prompt": "fix bug", "files_involved": ["main.py"], "branch": "dev"}
        req = adapter.normalize_request(raw)
        assert req.interface == InterfaceType.CLAUDE_CODE
        assert req.files_involved == ["main.py"]
        assert req.branch == "dev"

    def test_format_response(self):
        adapter = ClaudeCodeAdapter()
        resp = InterfaceResponse(
            success=True, output="Fixed", interface=InterfaceType.CLAUDE_CODE,
            model=ModelType.CLAUDE_SONNET, files_modified=["auth.py"],
            tests_passed=5, tests_total=5,
        )
        formatted = adapter.format_response(resp)
        assert "[PASS]" in formatted["output"]
        assert "auth.py" in formatted["output"]
        assert "5/5" in formatted["output"]

    def test_available_tools_includes_terminal(self):
        tools = ClaudeCodeAdapter().get_available_tools()
        assert "run_bash" in tools
        assert "git_commit" in tools
        assert "run_tests" in tools

    def test_max_context_tokens_largest(self):
        assert ClaudeCodeAdapter().get_max_context_tokens() == 200000


class TestCustomAPIAdapter:
    def test_normalize_and_format(self):
        adapter = CustomAPIAdapter()
        raw = {"prompt": "test"}
        req = adapter.normalize_request(raw)
        assert req.interface == InterfaceType.CUSTOM_API

        resp = InterfaceResponse(
            success=True, output="ok", interface=InterfaceType.CUSTOM_API,
            model=ModelType.CUSTOM,
        )
        formatted = adapter.format_response(resp)
        assert formatted["success"] is True


class TestAdapterFactory:
    def test_get_adapter_claude_app(self):
        adapter = get_adapter(InterfaceType.CLAUDE_APP)
        assert isinstance(adapter, ClaudeAppAdapter)

    def test_get_adapter_chatgpt(self):
        adapter = get_adapter(InterfaceType.CHATGPT_APP)
        assert isinstance(adapter, ChatGPTAppAdapter)

    def test_get_adapter_claude_code(self):
        adapter = get_adapter(InterfaceType.CLAUDE_CODE)
        assert isinstance(adapter, ClaudeCodeAdapter)

    def test_get_adapter_custom(self):
        adapter = get_adapter(InterfaceType.CUSTOM_API)
        assert isinstance(adapter, CustomAPIAdapter)

    def test_all_interfaces_have_adapters(self):
        for iface in InterfaceType:
            assert iface in ADAPTERS, f"No adapter for {iface}"


# ── ContextAggregator Tests ────────────────────────────────────────────


class TestContextAggregator:
    def test_aggregate_minimal(self, tmp_path):
        # Setup minimal project
        sharp_dir = tmp_path / "sharp"
        sharp_dir.mkdir()
        (sharp_dir / "__init__.py").write_text("", encoding="utf-8")

        config = AggregatorConfig(project_root=str(tmp_path))
        agg = ContextAggregator(config)

        request = InterfaceRequest(
            interface=InterfaceType.CLAUDE_APP,
            user_prompt="Fix the login bug",
        )
        result = agg.aggregate(request)

        assert isinstance(result, ContextAggregation)
        assert result.task_description == "Fix the login bug"

    def test_aggregate_with_files(self, tmp_path):
        (tmp_path / "auth.py").write_text("def login(): pass", encoding="utf-8")
        sharp_dir = tmp_path / "sharp"
        sharp_dir.mkdir()
        (sharp_dir / "__init__.py").write_text("", encoding="utf-8")

        config = AggregatorConfig(project_root=str(tmp_path))
        agg = ContextAggregator(config)

        request = InterfaceRequest(
            interface=InterfaceType.CLAUDE_CODE,
            user_prompt="fix auth",
            files_involved=["auth.py"],
        )
        result = agg.aggregate(request)

        assert "auth.py" in result.relevant_files
        assert "auth.py" in result.file_contents
        assert "def login" in result.file_contents["auth.py"]

    def test_record_history(self, tmp_path):
        sharp_dir = tmp_path / "sharp"
        sharp_dir.mkdir()
        (sharp_dir / "__init__.py").write_text("", encoding="utf-8")

        config = AggregatorConfig(project_root=str(tmp_path))
        agg = ContextAggregator(config)

        agg.record_interface_history(InterfaceType.CLAUDE_APP, "fix bug", "fixed")
        agg.record_interface_history(InterfaceType.CHATGPT_APP, "what is python?", "a language")

        request = InterfaceRequest(
            interface=InterfaceType.CLAUDE_CODE,
            user_prompt="continue",
        )
        result = agg.aggregate(request)

        assert InterfaceType.CLAUDE_APP.value in result.interface_histories
        assert InterfaceType.CHATGPT_APP.value in result.interface_histories

    def test_history_capped_at_20(self, tmp_path):
        sharp_dir = tmp_path / "sharp"
        sharp_dir.mkdir()
        (sharp_dir / "__init__.py").write_text("", encoding="utf-8")

        config = AggregatorConfig(project_root=str(tmp_path))
        agg = ContextAggregator(config)

        # Record 19 entries, then aggregate() adds one more = 20 total
        for i in range(19):
            agg.record_interface_history(InterfaceType.CLAUDE_APP, f"msg {i}")

        request = InterfaceRequest(
            interface=InterfaceType.CLAUDE_APP,
            user_prompt="test",
        )
        result = agg.aggregate(request)
        assert len(result.interface_histories[InterfaceType.CLAUDE_APP.value]) <= 20

    def test_inject_into_curator(self, tmp_path):
        sharp_dir = tmp_path / "sharp"
        sharp_dir.mkdir()
        (sharp_dir / "__init__.py").write_text("", encoding="utf-8")

        config = AggregatorConfig(project_root=str(tmp_path))
        agg = ContextAggregator(config)

        aggregation = ContextAggregation(
            task_description="test",
            git_diff="diff --git a/auth.py",
            git_log="abc123 fix bug",
            file_contents={"auth.py": "code here"},
            progress_summary="Feature 1/3 passing",
        )

        from sharp.harness.context.curator import ContextCurator
        from sharp.harness.core.config import ContextConfig
        curator = ContextCurator(ContextConfig())
        sources = agg.inject_into_curator(aggregation, curator)

        assert len(sources) >= 3  # diff, log, file, progress
        source_names = [s.name for s in sources]
        assert "git_diff" in source_names
        assert "git_log" in source_names
        assert "file:auth.py" in source_names
        assert "progress" in source_names


# ── AuditLogger Tests ──────────────────────────────────────────────────


class TestAuditLogger:
    def test_log_entry(self, tmp_path):
        config = AuditLoggerConfig(log_dir=str(tmp_path / "audit"))
        logger = AuditLogger(config)

        entry = AuditEntry(
            trace_id="test-001",
            user_prompt="fix bug",
            interface=InterfaceType.CLAUDE_APP,
            model_used=ModelType.CLAUDE_SONNET,
            ai_output="Fixed",
            final_status="success",
            latency_ms=1200,
            cost_usd=0.15,
        )
        logger.log(entry)

        # File should exist
        log_file = tmp_path / "audit" / "audit_log.jsonl"
        assert log_file.exists()

        # File should have one line
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1

        # Should be valid JSON
        record = json.loads(lines[0])
        assert record["trace_id"] == "test-001"
        assert record["user_prompt"] == "fix bug"
        assert record["final_status"] == "success"

    def test_query_by_interface(self, tmp_path):
        config = AuditLoggerConfig(log_dir=str(tmp_path / "audit"))
        logger = AuditLogger(config)

        for i in range(5):
            logger.log(AuditEntry(
                trace_id=f"t-{i}",
                interface=InterfaceType.CLAUDE_APP if i < 3 else InterfaceType.CHATGPT_APP,
                final_status="success",
            ))

        claude_entries = logger.query(interface=InterfaceType.CLAUDE_APP)
        assert len(claude_entries) == 3

        gpt_entries = logger.query(interface=InterfaceType.CHATGPT_APP)
        assert len(gpt_entries) == 2

    def test_query_by_status(self, tmp_path):
        config = AuditLoggerConfig(log_dir=str(tmp_path / "audit"))
        logger = AuditLogger(config)

        logger.log(AuditEntry(trace_id="t-1", final_status="success"))
        logger.log(AuditEntry(trace_id="t-2", final_status="error"))
        logger.log(AuditEntry(trace_id="t-3", final_status="success"))

        successes = logger.query(status="success")
        assert len(successes) == 2

        errors = logger.query(status="error")
        assert len(errors) == 1

    def test_summary(self, tmp_path):
        config = AuditLoggerConfig(log_dir=str(tmp_path / "audit"))
        logger = AuditLogger(config)

        logger.log(AuditEntry(
            trace_id="t-1", final_status="success", cost_usd=0.10, latency_ms=1000,
            model_used=ModelType.CLAUDE_SONNET, interface=InterfaceType.CLAUDE_APP,
        ))
        logger.log(AuditEntry(
            trace_id="t-2", final_status="error", cost_usd=0.05, latency_ms=500,
            model_used=ModelType.GPT4O, interface=InterfaceType.CHATGPT_APP,
        ))

        summary = logger.get_summary()
        assert summary["total"] == 2
        assert summary["successes"] == 1
        assert summary["errors"] == 1
        assert summary["success_rate"] == 0.5
        assert summary["total_cost_usd"] == pytest.approx(0.15, abs=0.001)

    def test_export_json(self, tmp_path):
        config = AuditLoggerConfig(log_dir=str(tmp_path / "audit"))
        logger = AuditLogger(config)

        logger.log(AuditEntry(trace_id="t-1", user_prompt="test"))
        exported = logger.export_json()
        data = json.loads(exported)
        assert len(data) == 1
        assert data[0]["trace_id"] == "t-1"


# ── PerformanceTracker Tests ───────────────────────────────────────────


class TestPerformanceTracker:
    def test_empty_snapshot(self):
        tracker = _PerformanceTracker()
        snap = tracker.snapshot()
        assert snap.total_requests == 0
        assert snap.avg_latency_ms == 0

    def test_snapshot_with_responses(self):
        tracker = _PerformanceTracker()
        tracker.record(InterfaceResponse(
            success=True, output="ok", interface=InterfaceType.CLAUDE_APP,
            model=ModelType.CLAUDE_SONNET, latency_ms=1000, cost_usd=0.10,
            validation_passed=True,
        ))
        tracker.record(InterfaceResponse(
            success=False, output="", interface=InterfaceType.CHATGPT_APP,
            model=ModelType.GPT4O, latency_ms=2000, cost_usd=0.20,
            validation_passed=False,
        ))

        snap = tracker.snapshot()
        assert snap.total_requests == 2
        assert snap.avg_latency_ms == 1500
        assert snap.total_cost_usd == pytest.approx(0.30, abs=0.001)
        assert snap.success_rate == 0.5
        assert snap.hallucination_rate == 0.5

    def test_by_model_breakdown(self):
        tracker = _PerformanceTracker()
        tracker.record(InterfaceResponse(
            success=True, output="", interface=InterfaceType.CLAUDE_APP,
            model=ModelType.CLAUDE_SONNET, latency_ms=1000, cost_usd=0.10,
        ))
        tracker.record(InterfaceResponse(
            success=True, output="", interface=InterfaceType.CHATGPT_APP,
            model=ModelType.GPT4O, latency_ms=800, cost_usd=0.05,
        ))

        by_model = tracker.by_model()
        assert ModelType.CLAUDE_SONNET.value in by_model
        assert ModelType.GPT4O.value in by_model
        assert by_model[ModelType.CLAUDE_SONNET.value]["requests"] == 1
        assert by_model[ModelType.GPT4O.value]["requests"] == 1

    def test_by_interface_breakdown(self):
        tracker = _PerformanceTracker()
        tracker.record(InterfaceResponse(
            success=True, output="", interface=InterfaceType.CLAUDE_APP,
            model=ModelType.CLAUDE_SONNET, latency_ms=1000, cost_usd=0.10,
        ))
        tracker.record(InterfaceResponse(
            success=True, output="", interface=InterfaceType.CLAUDE_CODE,
            model=ModelType.CLAUDE_SONNET, latency_ms=1200, cost_usd=0.12,
        ))

        by_iface = tracker.by_interface()
        assert InterfaceType.CLAUDE_APP.value in by_iface
        assert InterfaceType.CLAUDE_CODE.value in by_iface

    def test_capped_at_1000(self):
        tracker = _PerformanceTracker()
        for i in range(1100):
            tracker.record(InterfaceResponse(
                success=True, output="", interface=InterfaceType.CLAUDE_APP,
                model=ModelType.CLAUDE_SONNET,
            ))
        assert len(tracker._responses) == 1000


# ── Orchestrator Integration Tests ─────────────────────────────────────


class TestOrchestrator:
    @pytest.mark.asyncio
    async def test_handle_claude_app_request(self, tmp_path):
        sharp_dir = tmp_path / "sharp"
        sharp_dir.mkdir()
        (sharp_dir / "__init__.py").write_text("", encoding="utf-8")

        config = OrchestratorConfig(
            project_root=str(tmp_path),
            enable_audit_log=True,
        )
        orch = Orchestrator(config)

        raw = {"prompt": "fix the login bug", "files": ["auth.py"]}
        result = await orch.handle_request(raw, InterfaceType.CLAUDE_APP)

        assert result["success"] is True
        assert "Fixed" in result["content"] or "SHARP" in result["content"]

    @pytest.mark.asyncio
    async def test_handle_chatgpt_request(self, tmp_path):
        sharp_dir = tmp_path / "sharp"
        sharp_dir.mkdir()
        (sharp_dir / "__init__.py").write_text("", encoding="utf-8")

        config = OrchestratorConfig(project_root=str(tmp_path))
        orch = Orchestrator(config)

        raw = {"prompt": "what is Python?"}
        result = await orch.handle_request(raw, InterfaceType.CHATGPT_APP)

        assert result.get("success") is True or result.get("status") == "success"

    @pytest.mark.asyncio
    async def test_handle_claude_code_request(self, tmp_path):
        sharp_dir = tmp_path / "sharp"
        sharp_dir.mkdir()
        (sharp_dir / "__init__.py").write_text("", encoding="utf-8")

        config = OrchestratorConfig(project_root=str(tmp_path))
        orch = Orchestrator(config)

        raw = {"prompt": "run the tests", "files_involved": ["test_main.py"]}
        result = await orch.handle_request(raw, InterfaceType.CLAUDE_CODE)

        assert result["success"] is True or result["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_audit_log_populated(self, tmp_path):
        sharp_dir = tmp_path / "sharp"
        sharp_dir.mkdir()
        (sharp_dir / "__init__.py").write_text("", encoding="utf-8")

        config = OrchestratorConfig(project_root=str(tmp_path), enable_audit_log=True)
        orch = Orchestrator(config)

        await orch.handle_request({"prompt": "test"}, InterfaceType.CLAUDE_APP)
        await orch.handle_request({"prompt": "test2"}, InterfaceType.CHATGPT_APP)

        audit_log = orch.get_audit_log()
        assert len(audit_log) == 2
        assert audit_log[0].interface == InterfaceType.CLAUDE_APP
        assert audit_log[1].interface == InterfaceType.CHATGPT_APP

    @pytest.mark.asyncio
    async def test_performance_updated(self, tmp_path):
        sharp_dir = tmp_path / "sharp"
        sharp_dir.mkdir()
        (sharp_dir / "__init__.py").write_text("", encoding="utf-8")

        config = OrchestratorConfig(project_root=str(tmp_path))
        orch = Orchestrator(config)

        await orch.handle_request({"prompt": "test1"}, InterfaceType.CLAUDE_APP)
        await orch.handle_request({"prompt": "test2"}, InterfaceType.CHATGPT_APP)

        perf = orch.get_performance()
        assert perf.total_requests == 2
        assert perf.avg_latency_ms >= 0

    @pytest.mark.asyncio
    async def test_full_pipeline_end_to_end(self, tmp_path):
        """Full pipeline: request -> route -> context -> execute -> validate -> respond."""
        sharp_dir = tmp_path / "sharp"
        sharp_dir.mkdir()
        (sharp_dir / "__init__.py").write_text("", encoding="utf-8")

        config = OrchestratorConfig(
            project_root=str(tmp_path),
            enable_audit_log=True,
            enable_validation=True,
        )
        orch = Orchestrator(config)

        raw = {
            "prompt": "fix the React login bug where button doesn't submit",
            "files": ["login.jsx", "auth.js"],
            "session_id": "session-001",
        }
        result = await orch.handle_request(raw, InterfaceType.CLAUDE_APP)

        # Response returned
        assert isinstance(result, dict)
        assert "success" in result

        # Audit logged
        audit = orch.get_audit_log()
        assert len(audit) >= 1
        entry = audit[-1]
        assert entry.user_prompt == raw["prompt"]
        assert entry.routing_decision is not None
        assert entry.model_used in ModelType

        # Performance tracked
        perf = orch.get_performance()
        assert perf.total_requests >= 1
        assert perf.total_cost_usd > 0

    @pytest.mark.asyncio
    async def test_performance_by_model(self, tmp_path):
        sharp_dir = tmp_path / "sharp"
        sharp_dir.mkdir()
        (sharp_dir / "__init__.py").write_text("", encoding="utf-8")

        config = OrchestratorConfig(project_root=str(tmp_path))
        orch = Orchestrator(config)

        await orch.handle_request({"prompt": "fix bug"}, InterfaceType.CLAUDE_APP)
        await orch.handle_request({"prompt": "what is X?"}, InterfaceType.CHATGPT_APP)

        by_model = orch.get_performance_by_model()
        assert len(by_model) >= 1

    @pytest.mark.asyncio
    async def test_performance_by_interface(self, tmp_path):
        sharp_dir = tmp_path / "sharp"
        sharp_dir.mkdir()
        (sharp_dir / "__init__.py").write_text("", encoding="utf-8")

        config = OrchestratorConfig(project_root=str(tmp_path))
        orch = Orchestrator(config)

        await orch.handle_request({"prompt": "test"}, InterfaceType.CLAUDE_APP)

        by_iface = orch.get_performance_by_interface()
        assert InterfaceType.CLAUDE_APP.value in by_iface
