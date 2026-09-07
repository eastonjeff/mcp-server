# Using the MCP server with LangChain

This MCP server can be used as a tool provider for a LangChain agent. The
agent launches the server as a subprocess and communicates with it over MCP's
`stdio` transport.

```text
LangChain agent
    ↓
MCP adapter
    ↓ stdio
FastMCP server
    ├── PostgreSQL
    └── Ollama
```

## Install the LangChain packages

Activate the project's virtual environment and install the LangChain adapter
and Ollama integration:

```powershell
.\.venv\Scripts\Activate.ps1
pip install langchain langchain-mcp-adapters langchain-ollama
```

Make sure your `.env` contains the PostgreSQL and LLM settings described in
[README.md](README.md). Ollama must be running locally with the configured
model available.

## Example agent

Create a file such as `examples/langchain_agent.py`:

```python
import asyncio

from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama


PROJECT_ROOT = r"C:\dev\mcp-server"
PYTHON = rf"{PROJECT_ROOT}\.venv\Scripts\python.exe"


async def main() -> None:
    client = MultiServerMCPClient(
        {
            "sql": {
                "transport": "stdio",
                "command": PYTHON,
                "args": ["-m", "mcp_server.server"],
                "cwd": PROJECT_ROOT,
            }
        }
    )

    tools = await client.get_tools()
    model = ChatOllama(model="qwen2.5-coder:3b")
    agent = create_agent(model, tools)

    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "Find customers whose first name starts with John",
                }
            ]
        }
    )
    print(result["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(main())
```

Run it from the project root:

```powershell
python examples\langchain_agent.py
```

The agent can discover and call the MCP tools, including `list_tables`,
`describe_table`, `generate_query`, and `run_readonly_query`.

## SQL generation choices

There are two possible model flows:

1. LangChain decides which MCP tool to call, and `generate_query` calls Ollama
   to generate SQL.
2. LangChain calls database tools directly and generates SQL itself.

The first flow uses the server's schema-aware SQL generation and validation.
The second flow gives LangChain more control but requires you to implement
equivalent schema context, SQL validation, and read-only safeguards.

Avoid exposing `execute_generated_query` to an agent initially. It executes
model-generated SQL immediately. Prefer the safer sequence:

1. Call `generate_query`.
2. Review or validate the generated SQL.
3. Call `run_readonly_query`.

Even with read-only database transactions, generated queries can be expensive,
return sensitive data, or produce incorrect results. Add query timeouts, result
limits, and table allow-lists before using this pattern in production.
