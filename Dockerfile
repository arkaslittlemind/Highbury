# The analyst API as one container. Build from the repository root:
#   docker build -t highbury-api .
FROM python:3.12-slim

# The same uv version as the lock file was made with.
COPY --from=ghcr.io/astral-sh/uv:0.12.7 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# The lock covers the full workspace, so uv needs the manifest of each member.
# The code of the loaders does not go into the image.
COPY pyproject.toml uv.lock ./
COPY services/analyst/pyproject.toml services/analyst/pyproject.toml
COPY ingest/pyproject.toml ingest/pyproject.toml
# The dependencies are a layer of their own: a change of the source does not
# download them again.
RUN uv sync --frozen --no-dev --package analyst --no-install-workspace

COPY services/analyst/src services/analyst/src
RUN uv sync --frozen --no-dev --package analyst --no-editable

# The service writes no file, so it needs no rights of root.
RUN useradd --system --uid 1001 --no-create-home app
USER app

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

# The host sets the environment. uvicorn reads FORWARDED_ALLOW_IPS by itself.
# The access log is off: it writes the address of each visitor, and the service
# stores no personal data. The service writes its own line for each question.
CMD ["uvicorn", "analyst.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
