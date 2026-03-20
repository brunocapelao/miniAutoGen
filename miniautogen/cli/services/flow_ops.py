"""Flow management service for the CLI.

DA-9: New terminology wrappers around pipeline_ops.
These functions delegate to the existing pipeline_ops module.
"""

from __future__ import annotations

from miniautogen.cli.services.pipeline_ops import (
    create_pipeline,
    delete_pipeline,
    list_pipelines,
    show_pipeline,
    update_pipeline,
)

# New-name aliases
create_flow = create_pipeline
delete_flow = delete_pipeline
list_flows = list_pipelines
show_flow = show_pipeline
update_flow = update_pipeline

__all__ = [
    "create_flow",
    "delete_flow",
    "list_flows",
    "show_flow",
    "update_flow",
]
