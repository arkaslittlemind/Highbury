# Body limit comment and split-body test

| | |
| --- | --- |
| Work | Fix: a correct reason in one code comment, and one test that gives the app a request body in parts |
| Change | `5791411` on `main`, 2026-10-13 |
| Evidence | `blueprint/history/fixes/body-limit-comment-and-split-body-test.md` (spec, evidence, finding F-19. Local, not in Git). The commit message. The build conversation. `blueprint/context/findings.md` (F-23, F-24). |
| Reader | A learner who can write basic code and is new to this stack |

This document obeys the rules of ASD-STE100 Simplified Technical
English. It is not a certified STE document.

## 1. Summary

This fix repairs two small defects that the review of the body limit found.
One code comment gave a wrong reason, and the test suite did not guard one
path. The behavior of the service does not change, so the fix needs no deploy.

The one idea to remember: a test client is not a server. The test client gives
the app a full body as one message. A server gives a large body in parts.

## 2. Why this work exists

The body limit counts the bytes of a request body as the app reads them. The
study document of that fix explains the design.

The review of that fix found two defects (F-23 and F-24):

- A comment in `create_app` said that the CORS middleware must be outside the
  body limit. That was not true, and a wrong reason sends a reader to a rule
  that does not exist.
- Each test of the real app passed the limit in the first message. Thus no
  test showed the usual case, where the count passes the limit in a later message.

## 3. Design

The fix has two parts. No part changes a code line of the service.

| Part | Location | Job |
| --- | --- | --- |
| Comment | `services/analyst/src/analyst/api.py` (`create_app`) | States why the 413 has the CORS header in each order of the two middlewares. |
| Test | `services/analyst/tests/test_api.py` | Calls the app as a server does, with a body in three messages. |

One term is new in this work. A **scope** is the dictionary in which an ASGI
server describes one request: the method, the path, and the headers. The test
writes a scope by hand, because it calls the app without a server.

## 4. Workflow

Example input: the new test sends a body in three parts. Each part is one byte
more than half of the limit.

1. The test builds the app with the `serve` fixture and writes a scope for `POST /api/ask`. (`services/analyst/tests/test_api.py:397`)
2. The test calls the app with its own `receive` and `send` functions. (`services/analyst/tests/test_api.py:427`)
3. FastAPI reads the body. The body limit gets part 1, which is below the limit.
4. The body limit gets part 2. The count is now more than the limit.
5. The body limit raises `HTTPException(413)`. (`services/analyst/src/analyst/api.py:178`)
6. The exception handler of the app sends the 413 through the `send` function of the test.
7. The test asserts the status, the text, and that part 3 stays in the list. (`services/analyst/tests/test_api.py:433`)

The trace has three actors, and the study document of the body limit shows
them in a diagram. This document does not repeat it.

## 5. Decisions and tradeoffs

### 5.1 The test calls the app with no test client

- **Choice:** The test calls `client.app(scope, receive, send)` with `asyncio.run`.
- **Alternatives:** Give the test client a generator as the body.
- **Reason:** Recorded: the installed Starlette test client reads the full
  body first and gives the app one message. Source: finding F-24, which names
  `starlette/testclient.py:302`.
- **Cost:** The test writes the scope by hand, so it has more lines than the
  other tests. A new required key of ASGI can break it.

### 5.2 The order of the two middlewares stays

- **Choice:** Only the comment changes. `BodyLimit` stays inside the CORS middleware.
- **Alternatives:** Remove the comment, or change the order.
- **Reason:** Recorded: the order has no effect today, but it starts to matter
  if the body limit later sends a response by itself. Source: finding F-23.
- **Cost:** No test guards the order, because each order gives the same result.

### 5.3 The fix has no review of its own

- **Choice:** F-23 and F-24 have the status `fixed`, and the next audit of
  `api.py` examines them.
- **Alternatives:** An independent review before the merge, as for the body limit.
- **Reason:** Recorded: the fix changes a comment and adds a test, and it
  changes no behavior. Source: the Evidence section of the spec.
- **Cost:** Until that audit, no second reader confirmed the two repairs.

## 6. Blast radius

### 6.1 This work needs

| Dependency | Used for | If it fails |
| --- | --- | --- |
| The `serve` fixture | The app with a scripted model and a test database | The new test stops with an error before its first assertion. |
| The ASGI interface of FastAPI | The direct call of the app | The test fails, and the service is not affected. |

### 6.2 These things use this work

No consumers yet. No code calls a test, and a comment has no caller.

### 6.3 If you change this work

| If you change | Then check |
| --- | --- |
| `BodyLimit` so that it sends a response by itself | The comment in `create_app`, and the order of the two middlewares. |
| `MAX_BODY_BYTES` | Nothing. The test makes its parts from that value. |
| The path or the method of the ask route | The scope in the new test. |

### 6.4 How to remove this work

Revert the commit `5791411`. The service does not change, so no deploy is
necessary. The wrong comment comes back, and the suite loses one test.

## 7. Code reading path

1. [`services/analyst/src/analyst/api.py:465`](../services/analyst/src/analyst/api.py#L465) - Look for: the true reason that the 413 has the CORS header.
2. [`services/analyst/src/analyst/api.py:151`](../services/analyst/src/analyst/api.py#L151) - Look for: the class raises an error and sends no response.
3. [`services/analyst/tests/test_api.py:359`](../services/analyst/tests/test_api.py#L359) - Look for: the older test, where the test client gives one message.
4. [`services/analyst/tests/test_api.py:397`](../services/analyst/tests/test_api.py#L397) - Look for: the scope, the two functions, and the direct call of the app.
5. [`services/analyst/tests/test_api.py:433`](../services/analyst/tests/test_api.py#L433) - Look for: the proof that the app did not read part 3.

## 8. Known limits

- F-23 and F-24 are `fixed`, not `closed`. A later audit must examine them.
- The archive of this fix also holds F-19. The user decided to keep the ignore
  rule for `.gitkeep` files, so that finding is `accepted`. The root
  `.gitignore` still ends with no newline.
- The study document of the body limit describes the old comment. It is a
  record of that change and stays as it is.
- The new test does not use a real server. The independent review of the body
  limit did that check with the protocol classes of uvicorn.

## 9. Self-test

1. Why did the older tests not show the case of a body in parts?
2. Why does the 413 have the CORS header in each order of the two middlewares?
3. What happens if someone changes `BodyLimit` so that it sends the 413 by itself?
4. Why does the test assert that one part stays in the list?
5. Why does this fix need no deploy?

<details>
<summary>Answers</summary>

1. The test client reads the full body first and gives the app one message. See sections 1 and 5.1.
2. The exception handler of the app makes the 413, and that handler is inside the two middlewares. See sections 2 and 3.
3. Then the order matters, and the CORS middleware must be outside the body limit. See sections 5.2 and 6.3.
4. It proves that the read stopped at the part that passed the limit. See section 4.
5. The fix changes a comment and a test, and it changes no behavior of the service. See section 1.

</details>
