"""InitializerAgent: runs once at project start to create durable artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sharp.harness.artifacts.manager import ArtifactManager
from sharp.harness.artifacts.types import Feature
from sharp.harness.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class InitializerConfig:
    """Configuration for the InitializerAgent."""

    project_root: str = "."
    max_features: int = 200
    llm_model: str = "gpt-4o"


@dataclass
class InitializerResult:
    """Result from running the InitializerAgent."""

    success: bool
    features_created: int = 0
    artifacts: list[str] = field(default_factory=list)
    error: str = ""


# ── Default feature templates by category ─────────────────────────────

DEFAULT_FEATURE_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "core": [
        {
            "description": "Engine initializes with default config",
            "steps": [
                "Import HarnessEngine",
                "Create engine with default config",
                "Verify engine is not None",
            ],
        },
        {
            "description": "Engine runs full pipeline without LLM call",
            "steps": [
                "Create engine",
                "Call engine.run('test')",
                "Verify result is returned",
            ],
        },
        {
            "description": "HarnessConfig loads from YAML",
            "steps": [
                "Load harness.yaml",
                "Verify config fields populated",
            ],
        },
    ],
    "context": [
        {
            "description": "Context curator gathers and compresses sources",
            "steps": [
                "Create curator with config",
                "Add multiple context sources",
                "Call curate()",
                "Verify sources returned within token budget",
            ],
        },
        {
            "description": "Memory manager loads and persists state",
            "steps": [
                "Create memory manager",
                "Add key-value pair",
                "Verify retrieval",
            ],
        },
    ],
    "prompt": [
        {
            "description": "Prompt composer assembles system + context + tools",
            "steps": [
                "Create composer",
                "Provide user request, context sources, tools",
                "Verify augmented prompt has all sections",
            ],
        },
    ],
    "execution": [
        {
            "description": "ReAct loop executes Think-Act-Observe cycle",
            "steps": [
                "Create execution loop",
                "Provide mock LLM provider",
                "Run loop with tools",
                "Verify tool calls recorded",
            ],
        },
        {
            "description": "Tool registry registers and dispatches tools",
            "steps": [
                "Create tool registry",
                "Register async function",
                "Execute tool",
                "Verify result returned",
            ],
        },
        {
            "description": "Sub-agent manager spawns and returns results",
            "steps": [
                "Register sub-agent definition",
                "Spawn sub-agent with task",
                "Verify result returned",
            ],
        },
    ],
    "validation": [
        {
            "description": "Rule-based validator checks responses",
            "steps": [
                "Create validator",
                "Validate a response",
                "Verify pass/fail determined",
            ],
        },
        {
            "description": "LLM-as-judge evaluates response quality",
            "steps": [
                "Create LLM judge",
                "Evaluate a response",
                "Verify score returned",
            ],
        },
        {
            "description": "Retry engine mutates context on failure",
            "steps": [
                "Create retry engine",
                "Call mutate_for_retry with failed validation",
                "Verify context mutated",
            ],
        },
    ],
    "safety": [
        {
            "description": "Circuit breaker trips and recovers",
            "steps": [
                "Create circuit breaker",
                "Record N failures",
                "Verify state changes to OPEN",
                "Wait for recovery",
                "Verify state changes to HALF_OPEN",
            ],
        },
        {
            "description": "Budget manager enforces token/cost limits",
            "steps": [
                "Create budget manager with limits",
                "Record tokens approaching limit",
                "Verify BudgetExceededError raised",
            ],
        },
    ],
    "state": [
        {
            "description": "Checkpoint manager saves and loads state",
            "steps": [
                "Create checkpoint manager",
                "Save checkpoint with data",
                "Load checkpoint",
                "Verify data matches",
            ],
        },
        {
            "description": "Session manager handles lifecycle",
            "steps": [
                "Create session manager",
                "Start session",
                "Verify session active",
                "End session",
                "Verify session ended",
            ],
        },
    ],
    "mcp": [
        {
            "description": "MCP client connects to servers",
            "steps": [
                "Create MCP client",
                "Connect to server",
                "Verify connection established",
            ],
        },
        {
            "description": "MCP bridge converts tools/resources to SHARP format",
            "steps": [
                "Create MCP bridge",
                "Register tools",
                "Verify ToolDefinitions created",
            ],
        },
    ],
    "observability": [
        {
            "description": "Metrics collector tracks traces",
            "steps": [
                "Create metrics collector",
                "Start trace",
                "End trace with success",
                "Verify metrics recorded",
            ],
        },
    ],
    "integration": [
        {
            "description": "Full pipeline end-to-end (context -> prompt -> execute -> validate)",
            "steps": [
                "Create full engine",
                "Run with test request",
                "Verify complete pipeline executed",
                "Verify result returned",
            ],
        },
    ],
}


class InitializerAgent:
    """Runs once at project start to create all durable artifacts.

    Creates:
    - feature_list.json (200+ features, all passes=False)
    - progress.txt (empty header)
    - init.sh (startup script, if not provided)
    - git repo (initializes if not present)
    """

    def __init__(self, config: InitializerConfig | None = None) -> None:
        self.config = config or InitializerConfig()
        self.artifact_manager = ArtifactManager(self.config.project_root)

    async def run(self, user_spec: str = "") -> InitializerResult:
        """Execute the full initialization sequence.

        Args:
            user_spec: User's project specification or description.

        Returns:
            InitializerResult with success status and created artifacts.
        """
        project_root = Path(self.config.project_root)
        artifacts = []

        try:
            # Step 1: Create feature_list.json
            logger.info("Creating feature_list.json...")
            features = self._generate_features(user_spec)
            self.artifact_manager.write_features(features)
            artifacts.append("feature_list.json")

            # Step 2: Create progress.txt
            logger.info("Creating progress.txt...")
            self.artifact_manager.init_progress()
            artifacts.append("progress.txt")

            # Step 3: Verify init.sh exists
            if not self.artifact_manager.init_script_path.exists():
                logger.info("Creating init.sh...")
                self._create_init_script(project_root)
                artifacts.append("init.sh")
            else:
                logger.info("init.sh already exists")

            # Step 4: Initialize git if needed
            git_dir = project_root / ".git"
            if not git_dir.exists():
                logger.info("Initializing git repository...")
                self._init_git(project_root)
                artifacts.append(".git/")
            else:
                logger.info("Git repository already exists")

            completed, total = self.artifact_manager.get_completed_count()
            logger.info(
                f"Initialization complete: {total} features created, "
                f"{completed} passing"
            )

            return InitializerResult(
                success=True,
                features_created=len(features),
                artifacts=artifacts,
            )

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return InitializerResult(
                success=False,
                error=str(e),
                artifacts=artifacts,
            )

    def _generate_features(self, user_spec: str) -> list[Feature]:
        """Generate feature list from templates + user spec.

        Uses DEFAULT_FEATURE_TEMPLATES as the base. If the user provides
        a spec, it's included as metadata but doesn't change the template
        features (they cover the SHARP harness zones).
        """
        features: list[Feature] = []
        feature_id = 1

        for category, templates in DEFAULT_FEATURE_TEMPLATES.items():
            for template in templates:
                priority = 100 if category == "core" else 80
                if category in ("integration", "safety"):
                    priority = 60
                if category in ("mcp", "observability"):
                    priority = 40

                features.append(Feature(
                    id=f"{feature_id:02d}",
                    category=category,
                    description=template["description"],
                    steps=template["steps"],
                    passes=False,
                    priority=priority,
                ))
                feature_id += 1

        # Pad to max_features if needed
        while len(features) < self.config.max_features:
            features.append(Feature(
                id=f"{feature_id:02d}",
                category="extension",
                description=f"Extension feature {feature_id}",
                steps=["Define requirements", "Implement", "Test"],
                passes=False,
                priority=20,
            ))
            feature_id += 1

        return features[: self.config.max_features]

    def _create_init_script(self, project_root: Path) -> None:
        """Create init.sh startup script."""
        script = project_root / "init.sh"
        content = """#!/usr/bin/env bash
set -euo pipefail

# SHARP Enhanced — Dev Server Init
# Usage: bash init.sh

echo "=== SHARP Enhanced Init ==="

# Detect Python
PYTHON=""
if grep -qi microsoft /proc/version 2>/dev/null; then
  WIN_PYTHON="/mnt/c/Users/shiva/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"
  if [ -f "$WIN_PYTHON" ]; then
    PYTHON="$WIN_PYTHON"
  fi
fi
if [ -z "$PYTHON" ]; then
  for cmd in python3 python py; do
    if command -v "$cmd" &>/dev/null; then
      PYTHON="$cmd"
      break
    fi
  done
fi
if [ -z "$PYTHON" ]; then
  echo "ERROR: No Python found"
  exit 1
fi
echo "Using Python: $PYTHON"

# 1. Confirm directory
if [ ! -f "sharp/__init__.py" ]; then
  echo "ERROR: Not in harness_system directory"
  exit 1
fi
echo "[1/4] Directory confirmed"

# 2. Install package
echo "[2/4] Installing package..."
pip install -e "." -q 2>/dev/null && echo "  OK" || echo "  WARN: install failed"

# 3. Verify imports
echo "[3/4] Verifying imports..."
$PYTHON -c "from sharp import HarnessEngine, HarnessConfig; print('  Imports OK')" || {
  echo "  FATAL: Imports broken"
  exit 1
}

# 4. Smoke test
echo "[4/4] Running smoke test..."
$PYTHON -c "
from sharp import HarnessEngine
engine = HarnessEngine()
print('  Engine created OK')
" 2>&1 || {
  echo "  FATAL: Engine creation failed"
  exit 1
}

echo ""
echo "=== Init Complete ==="
echo "Ready for coding session."
"""
        script.write_text(content, encoding="utf-8")
        logger.info("Created init.sh")

    def _init_git(self, project_root: Path) -> None:
        """Initialize git repository."""
        import subprocess

        try:
            subprocess.run(
                ["git", "init"],
                cwd=str(project_root),
                capture_output=True,
                timeout=10,
            )
            # Create .gitignore if missing
            gitignore = project_root / ".gitignore"
            if not gitignore.exists():
                gitignore.write_text(
                    "__pycache__/\n*.pyc\n.pytest_cache/\n.harness/\n",
                    encoding="utf-8",
                )
            # Initial commit
            subprocess.run(
                ["git", "add", "-A"],
                cwd=str(project_root),
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit: SHARP Enhanced"],
                cwd=str(project_root),
                capture_output=True,
                timeout=10,
            )
            logger.info("Git repository initialized")
        except Exception as e:
            logger.warning(f"Git init failed (non-fatal): {e}")
