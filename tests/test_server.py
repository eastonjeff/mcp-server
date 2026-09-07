from mcp_server import server


class FakeDatabase:
    def list_tables(self) -> list[str]:
        return ["Customers"]

    def describe_table(self, table_name: str) -> list[dict[str, str]]:
        return [{"column_name": "FirstName", "data_type": "text"}]

    def execute_readonly(self, query: str) -> list[dict[str, str]]:
        return [{"FirstName": "John"}]


def test_execute_generated_query_returns_warning_query_and_rows(monkeypatch) -> None:
    monkeypatch.setattr(server, "database", FakeDatabase())
    monkeypatch.setattr(server, "generate_sql", lambda _prompt, _schema: 'SELECT "FirstName" FROM "Customers";')

    result = server.execute_generated_query("Find John")

    assert result["warning"].startswith("Generated SQL was executed")
    assert result["query"] == 'SELECT "FirstName" FROM "Customers";'
    assert result["row_count"] == 1
    assert result["rows"] == [{"FirstName": "John"}]
