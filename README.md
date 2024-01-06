# MiniAutoGen: A **Lightweight and Flexible** Library for Creating Agents and Multi-Agent Conversations

![MiniAutoGen Logo](miniautogen.png)

## About MiniAutoGen

MiniAutoGen is an innovative, open-source library designed for the next generation of applications in Large Language Models (LLMs). Focused on enabling [multi-agent conversations](docs/eng/multi_agent_chats.md), MiniAutoGen is celebrated for its lightweight and flexible structure. It's ideal for developers and researchers who aim to explore and expand the frontiers of conversational AI.

Drawing inspiration from [AutoGen](https://github.com/microsoft/autogen), MiniAutoGen offers a comprehensive suite of tools:
- **Unified Conversation Interface (`chat`):** Facilitates the creation and management of multi-agent conversations.
- **Coordination Mechanism (`chatadmin`):** Ensures efficient synchronization and management of agents.
- **Customizable Agents (`agent`):** Provides the flexibility to tailor agents according to specific needs.
- **Action Pipeline (`pipeline`):** Automates and streamlines agent operations, enhancing scalability and maintenance.

**Incorporating [LiteLLM](docs.litellm.ai/docs/), MiniAutoGen already integrates with over 100 LLMs. Use Bedrock, Azure, OpenAI, Cohere, Anthropic, Ollama, Sagemaker, HuggingFace, Replicate.**


## Why Choose MiniAutoGen?

### Multi-Agent Conversations
- **Complex Interactions:** Foster sophisticated dialogues involving multiple intelligent agents, each with unique abilities.

### Agent Customization
- **Tailored Behaviors:** Adapt agents to meet specific interaction requirements, enhancing the versatility of conversations.

### Flexibility and Modularity
- **Dynamic Conversations:** Shape engaging and responsive dialogues, with provisions for both automated and manual interventions.

### Effective Agent Coordination
- **Collaborative Goals:** Utilize our framework to facilitate seamless collaboration among agents towards common objectives.

### State-of-the-Art LLM Integration
- **Advanced AI Capabilities:** Leverage the power of Large Language Models to enrich conversations with intelligent and context-aware responses.

## Key Components

### [Agent](docs/eng/agent.md)
- **Dynamic Participants:** Each agent is an autonomous entity, capable of complex interactions and behaviors.

### [Chat](docs/eng/chat.md)
- **Conversation Management:** Handles group chat sessions, maintaining state and context for coherence and continuity.

### [ChatAdmin](docs/eng/chat_admin.md)
- **Orchestration:** Central to coordinating chat dynamics, ensuring efficient and harmonious agent collaboration.

### [Pipeline](docs/eng/pipeline.md)
- **Operational Efficiency:** Streamlines agent operations, enabling scalable and maintainable system architectures.

### [LLM Clients](docs/eng/llm_client.md)
- **AI-Powered Interactions:** Integrates diverse LLM clients, providing agents with sophisticated language processing tools.

### [Pipeline Components](docs/eng/components.md)

- **Simplified Development:** Our modular design makes it a breeze to create new pipeline components, empowering developers to tailor their conversational data processing and handling. This flexibility allows for the seamless integration of advanced AI features, including LLM responses, user interactions, and intricate decision-making processes, directly into the `agent` pipeline.

Explore our assortment of pre-built components, available [here](miniautogen/pipeline/components/components.py).


## Usage

**Install**
```pip install miniautogen```

**Iniciate a chat with a LLM**
```
#Initializing LLM Clients

import os
os.environ["OPENAI_API_KEY"] = "your-openai-key" 
from miniautogen.llms.llm_client import LiteLLMClient
openai_client = LiteLLMClient(model='gpt-3.5-turbo-16k')

# Building the Chat Environment

from miniautogen.chat.chat import Chat
from miniautogen.agent.agent import Agent
from miniautogen.chat.chatadmin import ChatAdmin
from miniautogen.pipeline.pipeline import Pipeline
from miniautogen.pipeline.components.components import (
    UserResponseComponent, AgentReplyComponent, TerminateChatComponent,
    Jinja2SingleTemplateComponent, LLMResponseComponent, NextAgentSelectorComponent
)

# Define a Jinja2 template for formatting messages
template_str = """
[{"role": "system", "content": "{{ agent.role }}"}{% for message in messages %},
  {% if message.sender_id == agent.agent_id %}
    {"role": "assistant", "content": {{ message.message | tojson | safe }}}
  {% else %}
    {"role": "user", "content": {{ message.message | tojson | safe }}}
  {% endif %}
{% endfor %}]
"""

# Initialize Jinja2 component with the template
jinja_component = Jinja2SingleTemplateComponent()
jinja_component.set_template_str(template_str)

# Set up pipelines for different components
pipeline_user = Pipeline([UserResponseComponent()])
pipeline_jinja = Pipeline([jinja_component, LLMResponseComponent(litellm_client)])
pipeline_admin = Pipeline([NextAgentSelectorComponent(), AgentReplyComponent(), TerminateChatComponent()])

# Create the chat environment
chat = Chat()

# Define agents with JSON data
json_data = {'agent_id': 'Bruno', 'name': 'Bruno', 'role': 'user'}
agent1 = Agent.from_json(json_data)
agent1.pipeline = pipeline_user  # Assign the user pipeline to agent1

agent2 = Agent("dev", "Carlos", "Python Senior Developer")
agent2.pipeline = pipeline_jinja  # Assign the LLM pipeline to agent2

# Add agents to the chat
chat.add_agent(agent1)
chat.add_agent(agent2)

# Add test messages to the chat
json_messages = [{'sender_id': 'Bruno', 'message': 'It’s a test, don’t worry'}]
chat.add_messages(json_messages)

# Initialize and configure ChatAdmin
chat_admin = ChatAdmin("admin", "Admin", "admin_role", pipeline_admin, chat, 10)

#running the chat
chat_admin.run()
```


## Exemples

### Using Multi-Agent Conversations to Develop a New Component for MiniAutoGen Itself

Multi-agent conversations represent interactions involving multiple agents, whether autonomous or human, each endowed with autonomy and specialized abilities. They work together to solve complex problems, share information, or perform specific tasks.

In this example, we will set up a conversation between two agents: one playing the role of a Product Owner and the other acting as an expert in developing MiniAutoGen components in Python.

The main goal of this test is to demonstrate the flexibility, ease, and efficiency of MiniAutoGen in creating and coordinating multi-agent conversations, as well as the simplicity in developing new components, thanks to the library's flexible design.


**The complete conversation history:** [chat_history.md](/exemples/multi-agent-develop/chat_history.md)

**View the notebook [here](/exemples/multi-agent-develop/Jinja2TemplatesComponent.ipynb)**

### Discover More Examples
For additional insights and inspiration, visit our [Examples folder](/exemples/). Here, you'll find a variety of scenarios demonstrating the versatility and capabilities of MiniAutoGen in different contexts.


## Contribute to MiniAutoGen

We invite AI enthusiasts, developers, and researchers to contribute and shape the future of multi-agent conversations. Your expertise can help evolve MiniAutoGen, creating more robust and diverse applications.

### How You Can Contribute:
- **Feature Development:** Enhance the framework by developing new features or refining existing ones.
- **Documentation & Tutorials:** Create clear guides and tutorials to facilitate user adoption.
- **Testing & Feedback:** Participate in testing and provide feedback for ongoing improvements.
- **Idea Sharing:** Contribute your innovative ideas and experiences to foster a vibrant community.

See more: [contribute](docs/eng/contribute.md)

---

MiniAutoGen: Pioneering the future of intelligent, interactive conversations.