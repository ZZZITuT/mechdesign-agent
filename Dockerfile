# MechDesign Agent - container image for the web app.
# Build:  docker build -t mechdesign-agent .
# Run:    docker run --rm -p 8000:8000 mechdesign-agent
#         (add -e ANTHROPIC_API_KEY=... to enable LLM interpretation)
#
# Only the [llm] extra is installed. anaStruct ([validation] extra, GPL-3.0) is
# deliberately left out so the image contains no GPL code; the FE cross-check
# then reports the anaStruct comparison as skipped.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MECHDESIGN_HOST=0.0.0.0 \
    MECHDESIGN_PORT=8000

WORKDIR /app
COPY pyproject.toml README.md LICENSE THIRD_PARTY_NOTICES.md ./
COPY src ./src
RUN pip install ".[llm]" && useradd --create-home --uid 10001 app

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else 1)"
CMD ["mechdesign", "serve"]
