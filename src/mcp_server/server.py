"""FastMCP server exposing read-only database discovery and SQL generation."""

from __future__ import annotations

import re

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

from mcp_server.database import Database
from mcp_server.sql_generator import generate_sql

load_dotenv(override=True)

mcp = FastMCP("SQL Learning Server")
database = Database()


@mcp.tool()
def list_tables() -> list[str]:
    """List the tables available in the configured read-only database."""
    return database.list_tables()


@mcp.tool()
def describe_table(table_name: str) -> list[dict[str, object]]:
    """Return column metadata for a table."""
    return database.describe_table(table_name)


@mcp.tool()
def generate_query(prompt: str) -> str:
    """Turn a natural-language request into one read-only SQL statement."""
    return _generate_query(prompt)


@mcp.tool()
def run_readonly_query(query: str) -> list[dict[str, object]]:
    """Execute a single read-only SELECT or WITH query and return its rows."""
    return database.execute_readonly(_validate_readonly_query(query))


@mcp.tool()
def execute_generated_query(prompt: str) -> dict[str, object]:
    """DANGEROUS: generate SQL from a prompt and execute it immediately.

    This executes model-generated SQL without a separate review step. Use
    generate_query and run_readonly_query instead when possible.
    """
    query = _generate_query(prompt)
    rows = database.execute_readonly(_validate_readonly_query(query))
    return {
        "warning": (
            "Generated SQL was executed immediately. Review generated SQL "
            "with generate_query before execution when possible."
        ),
        "prompt": prompt,
        "query": query,
        "row_count": len(rows),
        "rows": rows,
    }


def _generate_query(prompt: str) -> str:
    tables = database.list_tables()
    schema = {table: database.describe_table(table) for table in tables}
    return generate_sql(prompt, schema)


def _validate_readonly_query(query: str) -> str:
    normalized = query.strip().rstrip(";").strip()
    if not re.match(r"^(SELECT|WITH)\b", normalized, re.IGNORECASE):
        raise ValueError("Only SELECT and WITH queries are allowed.")
    if ";" in normalized:
        raise ValueError("Only one SQL statement is allowed.")
    return normalized


def main() -> None:
    """Run the server over stdio for MCP-compatible clients."""
    mcp.run()


if __name__ == "__main__":
    main()
