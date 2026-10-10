"""The parser lock: let one read-only SELECT on the agent's views through.

The SQL comes from a model that reads a visitor's question, so it is untrusted.
"""

import logging
import string
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

# The relations the agent can read. get_schema describes exactly these.
AGENT_VIEWS = ("v_matches", "v_shots", "v_player_match", "v_player_season", "v_passes")

# Each row goes into the model's context. 500 holds one player's shots of a season.
MAX_ROWS = 500

DIALECT = "postgres"

# sqlglot logs the text of a statement it cannot parse. That text is not for logs.
logging.getLogger("sqlglot").setLevel(logging.CRITICAL)

# These can be anywhere below a SELECT: a CTE that writes, SELECT INTO, FOR UPDATE.
FORBIDDEN_NODES = (exp.DML, exp.DDL, exp.Command, exp.Into, exp.Lock)

# Functions that change a session, signal other sessions, read files or large
# objects, or run a SQL string that this parser never sees.
FORBIDDEN_FUNCTION_PREFIXES = ("pg_", "lo_", "dblink")
FORBIDDEN_FUNCTIONS = ("set_config", "ts_stat", "ts_rewrite")
FORBIDDEN_FUNCTION_PARTS = ("_to_xml",)

# PostgreSQL folds only A to Z in a name without quotes. str.lower folds more:
# it makes the Kelvin sign a "k", so a name could pass as a different name.
ASCII_LOWER = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)


class SqlRejected(Exception):
    """The statement is not one read-only SELECT on the agent's views."""


@dataclass(frozen=True)
class Guarded:
    # The statement to run. It is written from the parsed tree, so the database
    # gets the statement that the guard checked and not the text that came in.
    sql: str
    # True when the row limit of the guard is the limit that applies.
    capped: bool


def guard(sql: str) -> Guarded:
    """Return the statement to run, with its row limit. Raise SqlRejected if not allowed."""
    try:
        return check(sql)
    except RecursionError:
        # sqlglot calls itself for each level when it parses and when it writes.
        raise SqlRejected("The SQL is nested too deeply.") from None


def check(sql: str) -> Guarded:
    try:
        sql.encode("utf-8")
    except UnicodeEncodeError:
        raise SqlRejected("The SQL has a character that the database cannot read.") from None
    if "\x00" in sql:
        # The client library ends the text at a NUL. The row limit comes after it.
        raise SqlRejected("The SQL has a NUL character.")

    try:
        statements = [s for s in sqlglot.parse(sql, read=DIALECT) if s is not None]
    except SqlglotError:
        raise SqlRejected("The SQL does not parse as PostgreSQL.") from None
    if not statements:
        raise SqlRejected("The SQL is empty.")
    if len(statements) > 1:
        raise SqlRejected("Only one statement is allowed.")
    (root,) = statements

    # An allowlist: sqlglot gives a statement it does not know a generic node.
    if not isinstance(root, exp.Select | exp.SetOperation):
        raise SqlRejected("Only a SELECT statement is allowed.")
    for node in root.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise SqlRejected("Only a read-only SELECT is allowed.")
        if isinstance(node, exp.Func):
            check_function(node)
    check_relations(root)

    capped_root, capped = cap_rows(root)
    return Guarded(capped_root.sql(dialect=DIALECT), capped)


def check_function(func: exp.Func) -> None:
    # An unknown function keeps its name in the node. A known one has a SQL name.
    name = func.name if isinstance(func, exp.Anonymous) else func.sql_name()
    name = name.translate(ASCII_LOWER)
    if (
        name.startswith(FORBIDDEN_FUNCTION_PREFIXES)
        or name in FORBIDDEN_FUNCTIONS
        or any(part in name for part in FORBIDDEN_FUNCTION_PARTS)
    ):
        raise SqlRejected(f"The function {name} is not allowed.")


def relation_name(identifier: exp.Identifier) -> str:
    """Return the name as PostgreSQL reads it."""
    return identifier.name if identifier.quoted else identifier.name.translate(ASCII_LOWER)


def check_relations(root: exp.Query) -> None:
    """Reject a relation that is not an agent view or a CTE that is in scope."""
    with_ = root.args.get("with_")
    for other in root.find_all(exp.With):
        # A CTE below the top has its own scope. Outside of that scope its name
        # is a real relation, so only the top WITH is supported.
        if other is not with_:
            raise SqlRejected("WITH is allowed only at the start of the statement.")
    if with_ is not None and with_.args.get("recursive"):
        raise SqlRejected("WITH RECURSIVE is not allowed.")

    allowed = set(AGENT_VIEWS)
    for cte in with_.expressions if with_ is not None else ():
        # A CTE sees only the CTEs before it. A later name is a real relation there.
        check_tables(cte, allowed)
        allowed.add(relation_name(cte.args["alias"].this))
    main = root.copy()
    main.set("with_", None)
    check_tables(main, allowed)


def check_tables(tree: exp.Expression, allowed: set[str]) -> None:
    for table in tree.find_all(exp.Table):
        source = table.this
        if isinstance(source, exp.Func):
            # A function in FROM, for example generate_series. check_function saw it.
            continue
        if not isinstance(source, exp.Identifier) or table.db or table.catalog:
            raise SqlRejected(f"The relation {table.sql(dialect=DIALECT)} is not allowed.")
        if relation_name(source) not in allowed:
            views = ", ".join(AGENT_VIEWS)
            raise SqlRejected(f"The relation {source.name} is not allowed. Use: {views}.")


def row_limit() -> exp.Limit:
    return exp.Limit(expression=exp.Literal.number(MAX_ROWS))


def cap_rows(root: exp.Query) -> tuple[exp.Query, bool]:
    """Return a query that gives MAX_ROWS rows at most, and True if the cap applies."""
    limit = root.args.get("limit")
    if limit is None:
        root.set("limit", row_limit())
        return root, True

    if isinstance(limit, exp.Limit):
        count = limit.expression
    else:
        # FETCH FIRST n ROWS ONLY. With PERCENT or WITH TIES the count is not a cap.
        options = limit.args.get("limit_options")
        special = options is not None and (
            options.args.get("percent") or options.args.get("with_ties")
        )
        count = None if special else limit.args.get("count")
    if isinstance(count, exp.Literal) and count.is_int:
        if int(count.this) <= MAX_ROWS:
            return root, False
        if isinstance(limit, exp.Limit):
            root.set("limit", row_limit())
            return root, True

    # A limit that is not a plain number can mean fewer rows than the cap or more.
    # The statement stays as it is, and the cap goes around it.
    return exp.select("*").from_(root.subquery("q")).limit(MAX_ROWS), True
