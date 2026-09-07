import pytest

from mcp_server.database import Database


class FakeCursor:
    def fetchall(self) -> list[dict[str, object]]:
        return [{"name": "John"}]


class FakeConnection:
    def __init__(self) -> None:
        self.queries: list[tuple[str, tuple[object, ...] | None]] = []

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, parameters: tuple[object, ...] | None = None) -> FakeCursor:
        self.queries.append((query, parameters))
        return FakeCursor()


def test_table_name_defaults_to_public_schema() -> None:
    assert Database._split_table_name("users") == ("public", "users")


def test_table_name_accepts_schema() -> None:
    assert Database._split_table_name("reporting.orders") == ("reporting", "orders")


@pytest.mark.parametrize("table_name", ["", "a.b.c", "users;DROP TABLE users", "bad-name"])
def test_table_name_rejects_unsafe_identifiers(table_name: str) -> None:
    with pytest.raises(ValueError):
        Database._split_table_name(table_name)


def test_readonly_query_preserves_percent_literals_without_parameters() -> None:
    connection = FakeConnection()
    database = Database("unused")
    database._connect = lambda: connection  # type: ignore[method-assign]

    assert database.execute_readonly("SELECT * FROM users WHERE name LIKE 'John%'") == [
        {"name": "John"}
    ]
    assert connection.queries == [("SELECT * FROM users WHERE name LIKE 'John%'", None)]
