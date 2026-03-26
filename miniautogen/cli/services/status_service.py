"""Status service -- aggregate workspace overview."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def get_workspace_status(project_root: Path) -> dict[str, Any]:
    """Aggregate workspace status from config, agents, flows, engines, server."""
    from miniautogen.cli.config import CONFIG_FILENAME, load_config
    from miniautogen.cli.services.agent_ops import list_agents
    from miniautogen.cli.services.engine_ops import list_engines
    from miniautogen.cli.services.pipeline_ops import list_pipelines
    from miniautogen.cli.services.server_ops import server_status

    config = load_config(project_root / CONFIG_FILENAME)
    agents = list_agents(project_root)
    flows = list_pipelines(project_root)
    engines = list_engines(project_root)
    server = server_status(project_root)

    return {
        "project": {
            "name": config.project.name,
            "version": config.project.version,
        },
        "server": server,
        "agents": {
            "count": len(agents),
            "names": [a.get("name", a.get("id", "?")) for a in agents],
        },
        "engines": {
            "count": len(engines),
            "names": [e.get("name", "?") for e in engines],
        },
        "flows": {
            "count": len(flows),
            "names": [f.get("name", "?") for f in flows],
        },
    }
