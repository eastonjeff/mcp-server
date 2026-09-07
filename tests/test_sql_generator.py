import json
from io import BytesIO

import pytest

from mcp_server import sql_generator


SCHEMA = {"users": [{"column_name": "id", "data_type": "integer"}]}


def test_generates_sql_from_openai_compatible_response(monkeypatch) -> None:
    response = BytesIO(
        json.dumps(
            {"choices": [{"message": {"content": "```sql\nSELECT id FROM users;\n```"}}]}
        ).encode()
    )
    monkeypatch.setattr(sql_generator.request, "urlopen", lambda *_args, **_kwargs: response)

    assert sql_generator.generate_sql("List user ids", SCHEMA) == 'SELECT "id" FROM "users";'


def test_quotes_mixed_case_table_returned_by_model(monkeypatch) -> None:
    response = BytesIO(
        json.dumps(
            {"choices": [{"message": {"content": "SELECT * FROM Customers"}}]}
        ).encode()
    )
    monkeypatch.setattr(sql_generator.request, "urlopen", lambda *_args, **_kwargs: response)

    assert sql_generator.generate_sql("List customers", {"Customers": []}) == (
        'SELECT * FROM "Customers";'
    )


def test_quotes_mixed_case_columns_in_filters(monkeypatch) -> None:
    response = BytesIO(
        json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": "SELECT Id, FirstName FROM Customers WHERE FirstName LIKE 'John%'"
                        }
                    }
                ]
            }
        ).encode()
    )
    monkeypatch.setattr(sql_generator.request, "urlopen", lambda *_args, **_kwargs: response)

    schema = {
        "Customers": [
            {"column_name": "Id", "data_type": "integer"},
            {"column_name": "FirstName", "data_type": "text"},
        ]
    }
    assert sql_generator.generate_sql("Find John", schema) == (
        'SELECT "Id", "FirstName" FROM "Customers" WHERE "FirstName" LIKE \'John%\';'
    )


def test_rejects_non_readonly_model_output(monkeypatch) -> None:
    response = BytesIO(
        json.dumps({"choices": [{"message": {"content": "DELETE FROM users"}}]}).encode()
    )
    monkeypatch.setattr(sql_generator.request, "urlopen", lambda *_args, **_kwargs: response)

    with pytest.raises(ValueError, match="unsafe SQL"):
        sql_generator.generate_sql("Remove users", SCHEMA)
