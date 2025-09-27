# Using Tools with Agents

One of the most powerful features of MiniAutoGen is the ability to equip agents with **Tools**. A Tool is a specific capability that an agent can decide to use to perform an action, such as searching the web, running code, or querying a database. This allows agents to go beyond simply generating text and interact with the outside world to gather information or perform tasks.

The tool system in MiniAutoGen is designed to be flexible and extensible, following the "Function Calling" paradigm seen in modern LLMs.

## Key Concepts

The architecture for using tools revolves around three main concepts:

1.  **The `Tool` Class:** An abstract base class that defines the contract for all tools.
2.  **`ToolSelectionComponent`:** A pipeline component that uses an LLM to decide *if* and *which* tool to use based on the conversation history.
3.  **`ToolExecutionComponent`:** A pipeline component that runs the selected tool with the arguments provided by the LLM.

---

## 1. Creating a Custom Tool

To create a new tool, you must inherit from the `miniautogen.tools.Tool` base class and implement the `execute` method.

### The `Tool` Base Class

-   `__init__(self, name: str, description: str)`:
    -   `name`: A short, descriptive name for the tool (e.g., "web_search", "calculator").
    -   `description`: A detailed explanation of what the tool does, what arguments it takes, and what it returns. **This description is critical**, as it's what the LLM uses to decide when to use the tool.
-   `execute(self, **kwargs) -> str`:
    -   This is the method that contains the actual logic of the tool. It receives its arguments as keyword arguments and must return a string representation of the output.

### Example: A Simple Calculator Tool

Here is how you would define a tool that can perform basic arithmetic:

```python
from miniautogen.tools import Tool

class CalculatorTool(Tool):
    def __init__(self):
        super().__init__(
            name="calculator",
            description="A simple calculator that can perform addition, subtraction, multiplication, and division. Takes two numbers (a, b) and an operator."
        )

    def execute(self, a: float, b: float, operator: str) -> str:
        # ... implementation of the calculator logic ...
        try:
            if operator == '+':
                return str(a + b)
            # ... handle other operators and errors ...
        except Exception as e:
            return f"Error: {e}"

```

---

## 2. Equipping an Agent with Tools

Once you have defined your tool(s), you can provide them to an `Agent` during its initialization using the `tools` parameter.

```python
from miniautogen.agent import Agent

# Instantiate your tool
calculator = CalculatorTool()

# Create an agent and give it the tool
math_agent = Agent(
    "math_expert",
    "MathExpert",
    "An AI expert that can solve math problems.",
    tools=[calculator]  # The agent now has the calculator tool
)
```

---

## 3. Building a Tool-Aware Pipeline

To make an agent use its tools, you need to construct a pipeline that includes the necessary components. The typical flow is:

`ToolSelectionComponent` -> `ToolExecutionComponent` -> `Jinja2SingleTemplateComponent` -> `LLMResponseComponent`

### Pipeline Breakdown

1.  **`ToolSelectionComponent`**:
    -   This component is the brain of the operation. It looks at the latest user message and the list of available tools for the agent.
    -   It then prompts an LLM, asking it to decide if a tool should be used. If the LLM says yes, it will also specify the tool's name and the arguments to use in a JSON format.
    -   This decision is stored in the pipeline state as `state.tool_call`.

2.  **`ToolExecutionComponent`**:
    -   This component checks if `state.tool_call` exists.
    -   If it does, it finds the corresponding tool in the agent's tool list and calls its `execute` method with the provided arguments.
    -   The result (the string returned by the tool) is stored in the pipeline state as `state.tool_output`.

3.  **`Jinja2SingleTemplateComponent`**:
    -   This component is responsible for preparing the final prompt for the LLM. To make it "tool-aware," you must create a template that can handle the output from the tool.
    -   The `tool_call` and `tool_output` variables are automatically passed to the Jinja2 template. You can use them to add the result of the tool execution into the prompt history. This gives the LLM the context it needs to formulate a final, human-readable answer.

    **Example of a tool-aware template:**
    ```jinja
    [
      {"role": "system", "content": "{{ agent.role }}"},
      {% for message in messages %}
        ... (standard message loop) ...
      {% endfor %}

      {# This is the crucial part for tools #}
      {% if tool_output %}
        ,{"role": "assistant", "content": "(I have used the '{{ tool_call.name }}' tool and got the result: {{ tool_output }}. Now I will formulate the final answer.)"}
      {% endif %}
    ]
    ```

4.  **`LLMResponseComponent`**:
    -   This final component takes the fully-formed prompt (which now includes the tool's output) and sends it to the LLM to generate the final answer.

By chaining these components together, you create a sophisticated workflow where an agent can reason about using a tool, execute it, and then use the result to complete its task. For a complete, runnable example, please see `exemples/tool_usage_example.ipynb`.