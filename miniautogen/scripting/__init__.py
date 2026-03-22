"""Scripting Mode — convenience API for rapid prototyping without YAML.

Provides an imperative Python API that abstracts away the full project
scaffolding (YAML config, workspace structure, engine profiles). Users can
define agents, tools, and flows purely in code, ideal for notebooks, scripts,
and quick experimentation.

Usage::

    from miniautogen.scripting import quick_run, ScriptBuilder

    # One-liner for simple tasks
    result = await quick_run(agent="gpt-4o", task="Summarize this text")

    # Builder pattern for multi-agent flows
    builder = ScriptBuilder()
    builder.add_agent("analyst", model="gpt-4o", role="Data analyst")
    builder.add_agent("reviewer", model="gpt-4o", role="Code reviewer")
    result = await builder.workflow(["analyst", "reviewer"], input="Analyze this CSV")

.. stability:: experimental
"""

from miniautogen.scripting.builder import ScriptBuilder
from miniautogen.scripting.quick import quick_run

__all__ = [
    "ScriptBuilder",
    "quick_run",
]
