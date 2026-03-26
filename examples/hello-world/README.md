# Hello World — MiniAutoGen

A minimal example to get started with MiniAutoGen in under 3 minutes.

## Quick Start

1. **Install MiniAutoGen** (if you haven't already):

   ```bash
   pip install miniautogen
   ```

2. **Set your API key:**

   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   ```

3. **Send a message:**

   ```bash
   miniautogen send "Hello! What can you do?" --agent assistant
   ```

4. **Start a chat session:**

   ```bash
   miniautogen chat assistant
   ```

5. **Run a workflow:**

   ```bash
   miniautogen run main --input "Tell me about Python async programming"
   ```

## Project Structure

```
hello-world/
  miniautogen.yaml    # Workspace configuration
  agents/
    assistant.yaml    # Agent definition
  .env.example        # API key template
```

## What's Next?

- Add more agents: `miniautogen agent create reviewer --role "Code Reviewer" --goal "Review code" --engine default_api`
- Create flows: `miniautogen flow create review --mode deliberation`
- Open the web console: `miniautogen console`
- Check workspace health: `miniautogen check`
