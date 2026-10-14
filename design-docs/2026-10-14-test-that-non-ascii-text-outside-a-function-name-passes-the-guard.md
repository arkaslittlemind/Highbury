# Test that non-ASCII text outside a function name passes the guard

| | |
| --- | --- |
| Work | Fix: one guard test shows that a player name with an accent still passes the SQL guard |
| Change | `8f9f549` on `main`, 2026-10-14 |
| Evidence | `blueprint/history/fixes/test-that-non-ascii-text-outside-a-function-name-passes-the-guard.md` (spec and closed finding F-26. Local, not in Git). The commit message. The build conversation. |
| Reader | A learner who can write basic code and is new to this stack |

This document obeys the rules of ASD-STE100 Simplified Technical
English. It is not a certified STE document.

## 1. Summary

This work adds one test and no product code. The test shows that the SQL guard
accepts letters outside ASCII in a string and in a quoted alias. It also shows
that the guard sends them to the database unchanged.

The one idea to remember: a test must protect a limit of a rule, not only the
rule. Here the limit is "function names only".

## 2. Why this work exists

The fix before this one made the guard reject a function name that is not ASCII.
See [Reject sequence write functions in the SQL guard](2026-10-14-reject-sequence-write-functions-in-the-sql-guard.md).
That rule is safe only because it stops at function names. Some player names
have letters outside ASCII, for example Robert Pirès. Thus `ILIKE '%Pirès%'` is
a normal query from the agent.

The independent review of that fix found F-26. No guard test used non-ASCII
text outside a function name. If a later change applied the rule to the whole
SQL text, every question about such a player would fail, and no test would
fail.

## 3. Design

The design is one parametrized test with two cases. A **parametrized test** is
one test function that pytest runs one time for each input. This work uses it
because the two cases need the same assertion.

| Part | Location | Job |
| --- | --- | --- |
| `test_text_outside_a_function_name_can_have_any_letter` | `services/analyst/tests/test_sql_guard.py` | Sends two queries to `guard` and checks that the returned SQL still holds the non-ASCII text. |
| `guard` | `services/analyst/src/analyst/sql_guard.py` | The code under test. It writes the SQL again from the parsed tree. |

The test checks the returned SQL, not only that `guard` raises no error. The
reason is that the database gets the SQL that `guard` writes, and a change in
sqlglot could change the text on the way.

This section has no diagram, because the work has only two parts.

## 4. Workflow

Example input: `SELECT player, goals FROM v_player_season WHERE player ILIKE '%Pirès%'`.

1. pytest calls the test with the query and the text `Pirès`. (`test_sql_guard.py:188`)
2. `guard` parses the query and finds no function call. (`sql_guard.py:87`)
3. `guard` writes the tree as SQL and adds `LIMIT 500`. (`sql_guard.py:91`)
4. The test checks that `Pirès` is in that SQL. (`test_sql_guard.py:189`)

The second case does the same with `SELECT goals AS "buts marqués" FROM
v_player_season` and the text `buts marqués`.

## 5. Decisions and tradeoffs

### 5.1 The test checks the written SQL

- **Choice:** Assert that the text is in `guard(sql).sql`.
- **Alternatives:** Add the two queries to
  `test_a_read_only_select_on_the_views_is_accepted`, which checks only that
  `guard` returns some SQL.
- **Reason:** Recorded: the database gets the SQL that the guard writes from the
  parsed tree, not the input text. Source: the spec, "The fix".
- **Cost:** One more test function in the file.

### 5.2 One literal and one quoted alias

- **Choice:** The cases are a string literal and a quoted alias.
- **Alternatives:** Only the literal, as F-26 suggested.
- **Reason:** Recorded: F-26 names "a non-ASCII literal or identifier". Source:
  F-26, "Why it matters". Inferred: a change could treat identifiers and
  literals in different ways. From the two node types that sqlglot uses for them.
- **Cost:** An unquoted non-ASCII alias has no case. The guard accepts it today.

### 5.3 The proof that the test can fail

- **Choice:** Before the commit, the builder made the rule cover the whole SQL
  text for a short time. Both cases failed. Then the builder removed that change.
- **Alternatives:** Trust that the test passes.
- **Reason:** Recorded: a test that cannot fail protects nothing. The spec puts
  this proof in the "Done when" of step 1. Source: the spec.
- **Cost:** None. The temporary change never went into Git.

## 6. Blast radius

### 6.1 This work needs

| Dependency | Used for | If it fails |
| --- | --- | --- |
| `guard` in `sql_guard.py` | The code under test | The test fails and names the case. |
| pytest | The test run | The Test command fails. |

### 6.2 These things use this work

No consumers yet. The work is a test, and no code imports it.

### 6.3 If you change this work

| If you change | Then check |
| --- | --- |
| The non-ASCII rule in `check_function` | This test, and `test_a_function_that_can_do_harm_is_rejected` |
| The version of sqlglot | This test shows if the written SQL loses an accent |

### 6.4 How to remove this work

Revert commit `8f9f549`. The guard does not change. No data and no configuration
stays behind.

## 7. Code reading path

1. [`test_sql_guard.py:180`](../services/analyst/tests/test_sql_guard.py#L180) - Look for: the comment that states the limit of the rule.
2. [`test_sql_guard.py:188`](../services/analyst/tests/test_sql_guard.py#L188) - Look for: the check on the written SQL.
3. [`sql_guard.py:102`](../services/analyst/src/analyst/sql_guard.py#L102) - Look for: the rule that this test keeps narrow.

## 8. Known limits

- An unquoted non-ASCII alias has no test case.
- The test does not run the query on the database. The audit did one manual
  run: `run_sql` with `ILIKE '%Pirès%'` returned Robert Pirès.
- The debrief found no new defect.

## 9. Self-test

1. Why does the test check the SQL that `guard` returns, and not only that it raises no error?
2. What happens to a question about Robert Pirès if the ASCII rule covers the whole SQL text?
3. How do you know that this test can fail?
4. Which case is missing from the test?
5. Why does the guard reject a non-ASCII function name but accept a non-ASCII string?

<details>
<summary>Answers</summary>

1. The database gets the written SQL, and a change in sqlglot could change the text. See section 5.1.
2. The guard rejects it, and this test fails. See section 2.
3. The builder made the rule wider for a short time, and both cases failed. See section 5.3.
4. An unquoted non-ASCII alias. See section 8.
5. Only a function name can turn into a different function on the way to the database. A player name must match the data. See section 2.

</details>
