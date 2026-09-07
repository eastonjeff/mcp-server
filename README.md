# FastMCP PostgreSQL server

A small learning project that exposes an existing PostgreSQL database through
an [MCP](https://modelcontextprotocol.io/) server. It is intentionally narrow:
inspect the schema, turn a natural-language request into SQL, and execute
read-only queries.

The `generate_query` tool sends the prompt and database schema to a configured
LLM through an OpenAI-compatible API, then validates the returned SQL before
passing it back to the MCP client.

## How the project is organized

```text
src/mcp_server/
  server.py         FastMCP application and tool definitions
  database.py       PostgreSQL connection, schema discovery, read-only queries
  sql_generator.py  LLM-backed prompt-to-SQL generation and validation
tests/              Unit tests for SQL generation and database helpers
```

The server exposes five tools:

| Tool | Purpose |
| --- | --- |
| `list_tables` | List tables visible to the configured database role |
| `describe_table` | Return columns and PostgreSQL data types |
| `generate_query` | Ask the configured LLM for a validated read-only query |
| `run_readonly_query` | Execute one `SELECT` or `WITH` query |
| `execute_generated_query` | Generate and execute a query immediately (dangerous) |

`database.py` sets PostgreSQL's `default_transaction_read_only` for every
connection. Still use a database role with only the permissions this server
needs; application-level checks are defense in depth, not authorization.

## Setup

Requires Python 3.11+ and network access to PostgreSQL.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

Edit `.env` with the connection string for your existing database:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/database_name
DB_CONNECT_TIMEOUT=5
```

The server and the VS Code launch profiles load `.env` automatically. Do not
put the connection string in a PowerShell profile or hard-code it in
`.vscode/launch.json`. Never commit `.env`; it is ignored by Git, while
`.env.example` is safe to commit.

Use the exact connection values from pgAdmin's connection properties:
**Host name/address**, **Port**, **Maintenance database** (usually the database
name), **Username**, and password. For example, a local database commonly uses
`localhost`, port `5432`, and `postgres`, but do not assume those values.

Before using the Inspector, test the same connection directly:

```powershell
python -c "from mcp_server.database import Database; print(Database().list_tables())"
```

If that command times out, compare `.env` with pgAdmin and check that the host,
port, database, username, and SSL settings match. `DB_CONNECT_TIMEOUT` limits
how long a connection attempt waits; it does not make an unavailable database
available.

## Run and test

Run the unit tests:

```powershell
py -m pytest
```

Confirm the FastMCP application imports and registers its tools:

```powershell
python -c "from mcp_server.server import mcp; print([tool.name for tool in mcp._tool_manager.list_tools()])"
```

Start the server:

```powershell
python -m mcp_server.server
```

### VS Code launch profiles

The project includes three profiles in `.vscode/launch.json`. Open the
**Run and Debug** view (`Ctrl+Shift+D`), select a profile, and press `F5`:

- **Launch MCP server** starts `mcp_server.server` with `.env` loaded. The
  server uses stdio and waits for an MCP client, so an idle terminal is
  expected.
- **Launch MCP Inspector** runs the MCP CLI's `dev` command for this server and
  opens the browser-based Inspector. It uses `.env` through
  `scripts/launch_inspector.py`; no PowerShell environment variable is needed.
- **Run tests** launches `pytest -q` with the same project environment. Set a
  breakpoint in a test or application file to debug it.

Select the Python interpreter from `.venv` when VS Code prompts for one. The
Python extension and its debugger (`debugpy`) must be installed. The launch
profiles load `.env`; environment variables configured by VS Code or the
terminal can still take precedence according to VS Code's environment rules.

The process waits for an MCP client. It is not an HTTP server and will appear
idle in the terminal; that is expected. Configure an MCP client or the MCP
Inspector to launch `mcp-sql-server` from this project environment. Then try:

1. `list_tables`
2. `describe_table` with a table name such as `users` or `reporting.orders`
3. `generate_query` with a request such as “show the first 10 orders”
4. Review the generated SQL, then call `run_readonly_query`

`execute_generated_query` combines steps 3 and 4. It is intentionally marked
**DANGEROUS** in the tool description and response because it executes
model-generated SQL without giving you a separate review step. Prefer
`generate_query`, inspect the SQL, and then call `run_readonly_query`.
Read-only mode prevents data modification, but it does not prevent expensive
queries, excessive result sets, sensitive data exposure, or incorrect results.

## Using an LLM for SQL generation

`generate_query` calls an OpenAI-compatible chat-completions endpoint. The
server sends the user's prompt plus the PostgreSQL schema, then validates the
response before returning it. The default configuration targets local Ollama:

### Ollama

[Ollama](https://ollama.com/) is a separate application that runs open-source
LLMs locally and exposes them through a local API. It is not installed inside
this Python project or virtual environment.

Download and install Ollama from the official page:

<https://ollama.com/download>

Verify the installation, download a model, and start the local service:

```powershell
ollama --version
ollama pull qwen2.5-coder:3b
ollama serve
```

Ollama normally listens on `http://localhost:11434`. The MCP server connects to
that endpoint using the following settings.

Set these values in `.env`:

```env
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen2.5-coder:3b
LLM_API_KEY=
LLM_TIMEOUT=60
```

If `generate_query` cannot reach Ollama, verify the service and model before
restarting the MCP Inspector:

```powershell
ollama list
Invoke-RestMethod http://localhost:11434/api/tags
```

`LLM_MODEL` must exactly match a name shown by `ollama list`, for example
`qwen2.5-coder:3b`. If Ollama is running on another host or port, update
`LLM_BASE_URL` accordingly. Ollama's OpenAI-compatible URL includes `/v1`.

For vLLM, LM Studio, or a hosted OpenAI-compatible service, change
`LLM_BASE_URL`, `LLM_MODEL`, and `LLM_API_KEY` as appropriate. Restart the MCP
server after changing `.env`.

Keep generation separate from execution. Model output is untrusted text:
the generator accepts only one `SELECT` or `WITH` statement, and the database
layer independently enforces read-only transactions. For production, add SQL
parsing, query timeouts, result-size limits, query logging, and schema/table
allow-lists.

## Open-source model options

These are good starting points for text-to-SQL experimentation. Run them
locally with Ollama, vLLM, or another OpenAI-compatible server, then call that
endpoint from Python.

- **Qwen2.5-Coder 3B/7B/14B** — strong code and SQL generation for its size; a
  practical local starting point.
- **DeepSeek-Coder V2 Lite** — capable coding model with useful SQL reasoning;
  check its memory requirements before choosing a larger variant.
- **SQLCoder** — specifically tuned for text-to-SQL; useful when SQL generation
  is the primary task rather than general conversation.
- **Qwen3-Coder** — newer coding-focused option; consider it when you have more
  GPU memory or a hosted inference endpoint.
- **Llama 3.1/3.2 Instruct** — broad ecosystem and easy local deployment; may
  need stronger schema/prompt constraints for reliable SQL.

### Hardware recommendations for less than 8 GB of VRAM

For a GPU with less than 8 GB of VRAM, start with a 3B–7B model in a 4-bit
quantized format. The model, context window, and runtime overhead all consume
VRAM, so avoid assuming that a model's parameter count is its total memory
requirement.

- **Best starting point:** Qwen2.5-Coder 3B or 7B at 4-bit quantization.
- **SQL-focused option:** SQLCoder in its smallest available quantized
  variant, if the model fits comfortably with your schema context.
- **Good fallback:** a 3B instruct/coder model with a concise schema prompt.
- **Avoid initially:** 14B+ models, large context windows, and unquantized
  weights.

With Ollama, try a 3B model first and keep the schema context focused on tables
relevant to the request. If a 7B model is slow, runs out of memory, or causes
the system to swap, move down to 3B or use a hosted endpoint. CPU inference
works for experimentation but will usually have noticeably higher latency.

Model quality depends heavily on schema context and evaluation. Start with a
small model and a fixed set of representative prompts, compare generated SQL
against expected queries, and only then consider fine-tuning or a larger model.
Check each model's license and hardware requirements before shipping it.

## Useful next steps

1. Add a `get_schema` tool that returns only the tables relevant to a request.
2. Add SQL parsing/validation and a configurable maximum row count.
4. Add integration tests against a disposable PostgreSQL instance.
5. Add query timing and audit logging without logging credentials or sensitive
   result data.
