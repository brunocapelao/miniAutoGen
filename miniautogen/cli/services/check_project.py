"""Project validation service.

Validates project structure, config, agent specs, skills, tools,
and environment. Returns a list of CheckResult.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from miniautogen.api import AgentSpec, SkillSpec, ToolSpec
from miniautogen.cli.config import ProjectConfig
from miniautogen.cli.models import CheckResult


def check_project(
    config: ProjectConfig,
    project_root: Path,
) -> list[CheckResult]:
    """Run all validation checks on a project.

    Returns a list of CheckResult (pass/fail per check).
    """
    results: list[CheckResult] = []
    results.append(_check_config_schema(config))
    results.extend(_check_agents(project_root, config))
    results.extend(_check_skills(project_root))
    results.extend(_check_tools(project_root))
    results.extend(_check_pipelines(config, project_root))
    results.extend(_check_pipeline_participants(config, project_root))
    results.extend(_check_engine_profiles(config, project_root))
    results.extend(_check_memory_profiles(config, project_root))
    results.extend(_check_environment(config))
    results.extend(_check_gateway_accessibility(config))
    return results


def _check_config_schema(config: ProjectConfig) -> CheckResult:
    """Verify config loaded successfully (already validated by Pydantic)."""
    return CheckResult(
        name="config_schema",
        passed=True,
        message="miniautogen.yaml is valid",
        category="static",
    )


def _check_agents(
    project_root: Path, config: ProjectConfig,
) -> list[CheckResult]:
    """Validate agent YAML files in agents/ directory."""
    results: list[CheckResult] = []
    agents_dir = project_root / "agents"
    if not agents_dir.is_dir():
        results.append(CheckResult(
            name="agents_dir",
            passed=True,
            message="No agents/ directory (optional)",
            category="static",
        ))
        return results

    for yaml_file in sorted(agents_dir.glob("*.yaml")):
        try:
            with yaml_file.open() as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                results.append(CheckResult(
                    name=f"agent:{yaml_file.name}",
                    passed=False,
                    message=f"Expected mapping, got {type(data).__name__}",
                    category="static",
                ))
                continue
            # Validate against AgentSpec schema
            try:
                AgentSpec.model_validate(data)
            except ValidationError as exc:
                results.append(CheckResult(
                    name=f"agent:{yaml_file.name}",
                    passed=False,
                    message=(
                        f"Schema validation error:"
                        f" {exc.error_count()} error(s)"
                    ),
                    category="static",
                ))
                continue
            has_sub_failures = False
            # Check engine_profile reference
            ep = data.get("engine_profile")
            if ep and ep not in config.engine_profiles:
                default_ep = config.defaults.engine
                if ep != default_ep:
                    has_sub_failures = True
                    results.append(CheckResult(
                        name=f"agent:{yaml_file.name}:engine",
                        passed=False,
                        message=f"Engine profile '{ep}' not found",
                        category="static",
                    ))
            # Check skill references
            skills = data.get("skills", {})
            attached = skills.get("attached", [])
            skills_dir = project_root / "skills"
            for skill_id in attached:
                skill_path = skills_dir / skill_id
                if not skill_path.is_dir():
                    has_sub_failures = True
                    results.append(CheckResult(
                        name=f"agent:{yaml_file.name}:skill:{skill_id}",
                        passed=False,
                        message=f"Skill '{skill_id}' not found in skills/",
                        category="static",
                    ))
            # Check tool references
            tool_access = data.get("tool_access", {})
            allowed_tools = tool_access.get("allow", [])
            tools_dir = project_root / "tools"
            for tool_name in allowed_tools:
                tool_file = tools_dir / f"{tool_name}.yaml"
                if not tool_file.is_file():
                    has_sub_failures = True
                    results.append(CheckResult(
                        name=f"agent:{yaml_file.name}:tool:{tool_name}",
                        passed=False,
                        message=f"Tool '{tool_name}' not found in tools/",
                        category="static",
                    ))

            if not has_sub_failures:
                results.append(CheckResult(
                    name=f"agent:{yaml_file.name}",
                    passed=True,
                    message="Valid",
                    category="static",
                ))
        except yaml.YAMLError as exc:
            results.append(CheckResult(
                name=f"agent:{yaml_file.name}",
                passed=False,
                message=f"YAML parse error: {exc}",
                category="static",
            ))

    return results


def _check_skills(project_root: Path) -> list[CheckResult]:
    """Validate skill directories have SKILL.md."""
    results: list[CheckResult] = []
    skills_dir = project_root / "skills"
    if not skills_dir.is_dir():
        return results

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        has_failure = False
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            has_failure = True
            results.append(CheckResult(
                name=f"skill:{skill_dir.name}",
                passed=False,
                message="Missing SKILL.md",
                category="static",
            ))
        # Validate skill.yaml if present
        skill_yaml = skill_dir / "skill.yaml"
        if skill_yaml.is_file():
            try:
                with skill_yaml.open() as f:
                    skill_data = yaml.safe_load(f)
                if isinstance(skill_data, dict):
                    SkillSpec.model_validate(skill_data)
            except ValidationError as exc:
                has_failure = True
                results.append(CheckResult(
                    name=f"skill:{skill_dir.name}:schema",
                    passed=False,
                    message=(
                        f"Schema validation error:"
                        f" {exc.error_count()} error(s)"
                    ),
                    category="static",
                ))
            except yaml.YAMLError as exc:
                has_failure = True
                results.append(CheckResult(
                    name=f"skill:{skill_dir.name}:yaml",
                    passed=False,
                    message=f"YAML parse error: {exc}",
                    category="static",
                ))
        if not has_failure:
            results.append(CheckResult(
                name=f"skill:{skill_dir.name}",
                passed=True,
                message="Valid",
                category="static",
            ))
    return results


def _check_tools(project_root: Path) -> list[CheckResult]:
    """Validate tool YAML files in tools/ directory."""
    results: list[CheckResult] = []
    tools_dir = project_root / "tools"
    if not tools_dir.is_dir():
        return results

    for yaml_file in sorted(tools_dir.glob("*.yaml")):
        try:
            with yaml_file.open() as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                results.append(CheckResult(
                    name=f"tool:{yaml_file.stem}",
                    passed=False,
                    message="Expected mapping",
                    category="static",
                ))
                continue
            try:
                ToolSpec.model_validate(data)
            except ValidationError as exc:
                results.append(CheckResult(
                    name=f"tool:{yaml_file.stem}",
                    passed=False,
                    message=(
                        f"Schema validation error:"
                        f" {exc.error_count()} error(s)"
                    ),
                    category="static",
                ))
                continue
            results.append(CheckResult(
                name=f"tool:{yaml_file.stem}",
                passed=True,
                message="Valid",
                category="static",
            ))
        except yaml.YAMLError as exc:
            results.append(CheckResult(
                name=f"tool:{yaml_file.stem}",
                passed=False,
                message=f"YAML parse error: {exc}",
                category="static",
            ))
    return results


def _check_pipelines(
    config: ProjectConfig, project_root: Path,
) -> list[CheckResult]:
    """Check pipeline targets are resolvable."""
    results: list[CheckResult] = []
    for name, pipeline_cfg in config.pipelines.items():
        target = pipeline_cfg.target
        if ":" not in target:
            results.append(CheckResult(
                name=f"pipeline:{name}",
                passed=False,
                message=f"Invalid target format: '{target}' (expected module:callable)",
                category="static",
            ))
            continue
        module_path, _ = target.rsplit(":", 1)
        # Check if module file exists relative to project
        file_path = project_root / module_path.replace(".", "/")
        try:
            resolved = file_path.with_suffix(".py").resolve()
            project_resolved = project_root.resolve()
            if not str(resolved).startswith(str(project_resolved)):
                results.append(CheckResult(
                    name=f"pipeline:{name}",
                    passed=False,
                    message=f"Target '{target}' resolves outside project",
                    category="static",
                ))
                continue
        except (OSError, ValueError):
            pass
        if file_path.with_suffix(".py").is_file() or (file_path / "__init__.py").is_file():
            results.append(CheckResult(
                name=f"pipeline:{name}",
                passed=True,
                message=f"Target '{target}' resolvable",
                category="static",
            ))
        else:
            results.append(CheckResult(
                name=f"pipeline:{name}",
                passed=False,
                message=f"Module '{module_path}' not found",
                category="static",
            ))
    return results


def _check_engine_profiles(
    config: ProjectConfig, project_root: Path,
) -> list[CheckResult]:
    """Check default engine profile exists."""
    results: list[CheckResult] = []
    default_ep = config.defaults.engine
    if default_ep not in config.engine_profiles:
        results.append(CheckResult(
            name="default_engine_profile",
            passed=False,
            message=f"Default profile '{default_ep}' not defined",
            category="static",
        ))
    else:
        results.append(CheckResult(
            name="default_engine_profile",
            passed=True,
            message=f"Default profile '{default_ep}' exists",
            category="static",
        ))
    return results


def _check_memory_profiles(
    config: ProjectConfig, project_root: Path,
) -> list[CheckResult]:
    """Check memory profiles exist."""
    results: list[CheckResult] = []
    default_mp = config.defaults.memory_profile
    if config.memory_profiles and default_mp not in config.memory_profiles:
        results.append(CheckResult(
            name="default_memory_profile",
            passed=False,
            message=f"Default profile '{default_mp}' not defined",
            category="static",
        ))
    else:
        results.append(CheckResult(
            name="default_memory_profile",
            passed=True,
            message="Memory profiles valid",
            category="static",
        ))
    return results


def _check_environment(
    config: ProjectConfig,
) -> list[CheckResult]:
    """Check environment variables for configured providers."""
    results: list[CheckResult] = []

    _PROVIDER_ENV: dict[str, str] = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "google": "GOOGLE_API_KEY",
    }

    checked_providers: set[str] = set()
    for _ep_name, ep in config.engine_profiles.items():
        provider = ep.provider.lower()
        if provider in checked_providers or provider == "litellm":
            continue
        checked_providers.add(provider)
        env_var = _PROVIDER_ENV.get(provider)
        if env_var and not os.environ.get(env_var):
            results.append(CheckResult(
                name=f"env:{env_var}",
                passed=False,
                message=f"Missing {env_var} for provider '{ep.provider}'",
                category="environment",
            ))
        elif env_var:
            results.append(CheckResult(
                name=f"env:{env_var}",
                passed=True,
                message=f"{env_var} is set",
                category="environment",
            ))

    return results


def _check_pipeline_participants(
    config: ProjectConfig, project_root: Path,
) -> list[CheckResult]:
    """Validate that pipeline participants reference existing agents."""
    results: list[CheckResult] = []
    agents_dir = project_root / "agents"

    # Read raw YAML to check participants (not in PipelineConfig model)
    config_path = project_root / "miniautogen.yaml"
    if not config_path.is_file():
        return results

    raw = yaml.safe_load(config_path.read_text())
    if not isinstance(raw, dict):
        return results

    pipelines = raw.get("flows", raw.get("pipelines", {}))
    for pname, pcfg in pipelines.items():
        if not isinstance(pcfg, dict):
            continue
        participants = pcfg.get("participants", [])
        leader = pcfg.get("leader")

        for agent_name in participants:
            agent_file = agents_dir / f"{agent_name}.yaml"
            if not agent_file.is_file():
                results.append(CheckResult(
                    name=f"pipeline:{pname}:participant:{agent_name}",
                    passed=False,
                    message=f"Agent '{agent_name}' referenced in pipeline '{pname}' not found",
                    category="static",
                ))

        if leader:
            leader_file = agents_dir / f"{leader}.yaml"
            if not leader_file.is_file():
                results.append(CheckResult(
                    name=f"pipeline:{pname}:leader:{leader}",
                    passed=False,
                    message=f"Leader '{leader}' referenced in pipeline '{pname}' not found",
                    category="static",
                ))

    return results


def _check_gateway_accessibility(
    config: ProjectConfig,
) -> list[CheckResult]:
    """Check if local gateway endpoints are accessible.

    If any engine profile has a localhost endpoint, verify the
    gateway is reachable. Reports warning if not.
    """
    import urllib.error
    import urllib.request

    results: list[CheckResult] = []
    local_endpoints: set[str] = set()

    # Also check raw YAML for endpoint field (not in EngineProfileConfig model)
    for _ep_name, ep in config.engine_profiles.items():
        # EngineProfileConfig doesn't have an endpoint field by default,
        # but raw YAML may. Check model_extra or provider hints.
        provider = ep.provider.lower()
        if provider in ("vllm", "gemini-cli"):
            local_endpoints.add("http://localhost:8080")

    if not local_endpoints:
        return results

    for endpoint in local_endpoints:
        try:
            health_url = f"{endpoint}/health"
            req = urllib.request.Request(health_url, method="GET")
            urllib.request.urlopen(req, timeout=2)
            results.append(CheckResult(
                name=f"gateway:{endpoint}",
                passed=True,
                message=f"Gateway at {endpoint} is accessible",
                category="environment",
            ))
        except (urllib.error.URLError, OSError):
            results.append(CheckResult(
                name=f"gateway:{endpoint}",
                passed=True,
                message=(
                    f"WARN: Gateway at {endpoint} is not accessible. "
                    f"Run 'miniautogen server start' to start it."
                ),
                category="environment",
                warning=True,
            ))

    return results
