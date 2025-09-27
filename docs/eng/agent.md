# Agent
## Overview

The `Agent` class is a fundamental component of the MiniAutoGen library, representing an autonomous entity that can participate in conversations. Each agent is defined by its identity, role, and a processing pipeline that dictates its behavior.

This document provides a detailed description of the `Agent` class, its attributes, methods, and example usage.

## Class Definition: `miniautogen.agent.agent.Agent`

The `Agent` class models an agent with specific attributes and capabilities, essential for dynamic interactions in the multi-agent system.

#### Attributes:
- `agent_id` (`str`): Uniquely identifies the agent within the system.
- `name` (`str`): The human-readable name of the agent.
- `role` (`str`): The designated role or function of the agent within a conversation or task.
- `pipeline` (`Pipeline`, optional): An object representing the processing pipeline of the agent. If not specified, defaults to `None`.
- `status` (`str`): The current state of the agent (e.g., "available", "busy").

### Methods

##### `__init__(self, agent_id, name, role, pipeline=None)`

Initializes a new `Agent` instance.

- **Parameters**:
  - `agent_id` (`str`): The unique identifier for the agent.
  - `name` (`str`): The name of the agent.
  - `role` (`str`): The role of the agent.
  - `pipeline` (`Pipeline`, optional): The processing pipeline for the agent.

##### `generate_reply(self, state)`

Generates a response by processing the current state through its pipeline.

- **Parameters**:
  - `state` (`State`): The current state of the conversation to be processed.
- **Returns**:
  - `str`: The generated reply.

##### `get_status(self)`

Retrieves the current status of the agent.

- **Returns**:
  - `str`: The agent's current status.

##### `from_json(json_data)`

A static method that creates an `Agent` instance from a JSON object.

- **Parameters**:
  - `json_data` (`dict`): A dictionary containing agent data.
- **Returns**:
  - `Agent`: A new `Agent` instance.
- **Raises**:
  - `ValueError`: If the JSON data is missing any of the required keys (`agent_id`, `name`, `role`).

---

## Example Usage

### Creating a Basic Agent

Here's how to create a simple agent without a pipeline:

```python
from miniautogen.agent import Agent

# Create an agent with a unique ID, name, and role
my_agent = Agent(agent_id="chatbot_1", name="ChatBot", role="Responder")

print(f"Agent '{my_agent.name}' is ready.")
```

### Creating an Agent from JSON

You can also initialize an agent using a dictionary:

```python
json_data = {"agent_id": "databot_2", "name": "DataBot", "role": "Analyzer"}
data_agent = Agent.from_json(json_data)

print(f"Agent '{data_agent.name}' created from JSON.")
```

### Using an Agent with a Pipeline

For an agent to do useful work, it needs a `Pipeline`.

```python
from miniautogen.pipeline import Pipeline
from miniautogen.pipeline.components import LLMResponseComponent, Jinja2SingleTemplateComponent
from miniautogen.llms.llm_client import LiteLLMClient

# Assume llm_client and a chat environment are set up
llm_client = LiteLLMClient(model="gpt-3.5-turbo")
agent_pipeline = Pipeline([
    Jinja2SingleTemplateComponent(), # Assume template is set
    LLMResponseComponent(llm_client)
])

# Create an agent with a pipeline
pipeline_agent = Agent(
    agent_id="smartbot_3",
    name="SmartBot",
    role="A helpful assistant.",
    pipeline=agent_pipeline
)

# The agent's generate_reply method would now execute this pipeline
# reply = pipeline_agent.generate_reply(current_state)
```