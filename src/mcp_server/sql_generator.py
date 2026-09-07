"""Prompt-to-SQL generation through an OpenAI-compatible chat endpoint."""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError

from dotenv import load_dotenv

load_dotenv(override=True)


def generate_sql(prompt: str, schema: dict[str, list[dict[str, Any]]]) -> str:
    """Ask the configured LLM to generate one read-only PostgreSQL query."""
    if not prompt.strip():
        raise ValueError("Prompt cannot be empty.")
    if not schema:
        raise ValueError("No database tables are available.")

    base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "qwen2.5-coder:7b")
    api_key = os.getenv("LLM_API_KEY", "")
    timeout = _timeout()
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You generate PostgreSQL SQL. Return exactly one read-only "
                    "SELECT or WITH statement and no explanation. Never use "
                    "INSERT, UPDATE, DELETE, DDL, or multiple statements. "
                    "Use only tables and columns from the supplied schema. Preserve "
                    "their exact spelling and capitalization; double-quote any "
                    "mixed-case identifiers, such as \"Customers\" or \"FirstName\". "
                    "Add LIMIT 100 unless the user requests a smaller limit."
                ),
            },
            {
                "role": "user",
                "content": f"Schema:\n{json.dumps(schema, indent=2, default=str)}\n\n"
                f"Request: {prompt}",
            },
        ],
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    http_request = request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            result = json.load(response)
    except HTTPError as error:
        try:
            detail = error.read().decode("utf-8", errors="replace")
        except OSError:
            detail = error.reason
        raise RuntimeError(
            f"LLM request returned HTTP {error.code} from {base_url}: {detail}"
        ) from error
    except (OSError, TimeoutError, URLError) as error:
        raise RuntimeError(
            f"LLM request failed at {base_url}. Check LLM_BASE_URL, LLM_MODEL, "
            f"and that the model server is running. Details: {error}"
        ) from error

    try:
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("LLM response did not contain chat completion content.") from error
    column_names = tuple(
        column["column_name"]
        for columns in schema.values()
        for column in columns
        if isinstance(column.get("column_name"), str)
    )
    return _validate_sql(content, tuple(schema), column_names)


def _timeout() -> float:
    try:
        value = float(os.getenv("LLM_TIMEOUT", "60"))
    except ValueError as error:
        raise ValueError("LLM_TIMEOUT must be a number of seconds.") from error
    if value <= 0:
        raise ValueError("LLM_TIMEOUT must be greater than zero.")
    return value


def _validate_sql(
    content: str,
    table_names: tuple[str, ...] = (),
    column_names: tuple[str, ...] = (),
) -> str:
    sql = re.sub(r"```(?:sql)?", "", content, flags=re.IGNORECASE).strip().rstrip(";").strip()
    if not re.match(r"^(SELECT|WITH)\b", sql, re.IGNORECASE) or ";" in sql:
        raise ValueError("LLM returned unsafe SQL; expected one SELECT or WITH statement.")
    normalized_sql = _quote_known_tables(sql, table_names)
    return f"{_quote_known_columns(normalized_sql, column_names)};"


def _quote_known_tables(sql: str, table_names: tuple[str, ...]) -> str:
    """Quote known mixed-case table names the model returned without quotes."""
    by_lower_name = {name.lower(): name for name in table_names}

    def replace_table(match: re.Match[str]) -> str:
        keyword, identifier = match.group(1), match.group(2)
        exact_name = by_lower_name.get(identifier.lower())
        if exact_name is None or identifier.startswith('"'):
            return match.group(0)
        quoted_name = ".".join(f'"{part}"' for part in exact_name.split("."))
        return f"{keyword} {quoted_name}"

    return re.sub(
        r"(?i)\b(FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)",
        replace_table,
        sql,
    )


def _quote_known_columns(sql: str, column_names: tuple[str, ...]) -> str:
    """Quote known column names outside SQL string and identifier literals."""
    by_lower_name = {name.lower(): name for name in column_names}
    token_pattern = re.compile(
        r"""'(?:''|[^'])*'|"(?: doubled quote|[^"])*"|[A-Za-z_][A-Za-z0-9_]*""".replace(
            " doubled quote", '""'
        )
    )

    def replace_token(match: re.Match[str]) -> str:
        token = match.group(0)
        if token.startswith(("'", '"')):
            return token
        exact_name = by_lower_name.get(token.lower())
        return f'"{exact_name}"' if exact_name else token

    return token_pattern.sub(replace_token, sql)
