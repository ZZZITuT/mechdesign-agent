"""FastAPI web server: a thin HTTP layer over the engine and the language layer.

Start it with ``mechdesign serve`` (or ``uvicorn mechdesign.server:app``).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, report
from . import mechanics as M
from .crosscheck import cross_check
from .language import llm, service

WEB_DIR = Path(__file__).resolve().parent / "web"

app = FastAPI(
    title="MechDesign Agent",
    version=__version__,
    description="Rectangular cantilever sensor-mount design explorer. All numbers come from a deterministic engine.",
)


class ConfigBody(BaseModel):
    config: dict[str, Any] = Field(description="Configuration in display units; see examples/example_config.json.")


class InterpretBody(BaseModel):
    message: str
    config: dict[str, Any]


class ExplainBody(BaseModel):
    config: dict[str, Any]
    message: str = ""
    selected_id: str | None = None


class CrossCheckBody(BaseModel):
    config: dict[str, Any]
    b_mm: float | None = None
    h_mm: float | None = None
    poisson: float = 0.3


class ReportBody(BaseModel):
    config: dict[str, Any]
    selected_id: str | None = None
    format: Literal["html", "md"] = "html"
    include_explanation: bool = True
    message: str = ""


def _invalid(e: M.InputError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": "invalid_input", "errors": e.as_list()})


def _field_error(field: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=422, content={"error": "invalid_input", "errors": [{"field": field, "message": message}]}
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/api/status")
def status() -> dict[str, Any]:
    return {
        "version": __version__,
        "llm_enabled": llm.llm_enabled(),
        "llm_model": llm.model_name() if llm.llm_enabled() else None,
        "fallback_label": service.FALLBACK_LABEL,
    }


@app.get("/api/example")
def example() -> dict[str, Any]:
    return {
        "config": M.EXAMPLE_CONFIG,
        "materials": M.MATERIAL_PRESETS,
        "assumptions": M.MODEL_ASSUMPTIONS,
        "limitations": M.MODEL_LIMITATIONS,
    }


@app.post("/api/run")
def run(body: ConfigBody) -> Any:
    try:
        return M.run_problem(body.config)
    except M.InputError as e:
        return _invalid(e)


@app.post("/api/interpret")
def interpret(body: InterpretBody) -> Any:
    current = None
    try:
        p = M.parse_config(body.config)
        current = M.evaluation_to_display(M.evaluate(p.design, p.requirements))
    except M.InputError:
        current = None  # interpretation can still help fix an invalid form
    return service.interpret_request(body.message, body.config, current)


@app.post("/api/explain")
def explain(body: ExplainBody) -> Any:
    try:
        out = M.run_problem(body.config)
    except M.InputError as e:
        return _invalid(e)
    return service.explain_results(out, body.message, report.find_candidate(out, body.selected_id))


@app.post("/api/crosscheck")
def crosscheck(body: CrossCheckBody) -> Any:
    try:
        p = M.parse_config(body.config)
    except M.InputError as e:
        return _invalid(e)
    d = p.design
    if body.b_mm is not None and body.h_mm is not None:
        try:
            d = M.BeamDesign(d.L, body.b_mm / 1000.0, body.h_mm / 1000.0, d.E, d.rho, d.F)
            M.validate_design(d)
        except M.InputError as e:
            return _invalid(e)
    if not (0 < body.poisson < 0.5):
        return _field_error("poisson", "Poisson's ratio must be between 0 and 0.5.")
    return cross_check(d, nu=body.poisson)


@app.post("/api/report")
def make_report(body: ReportBody) -> Any:
    try:
        text = report.generate_report(
            body.config, body.selected_id, body.format, body.message, body.include_explanation
        )
    except M.InputError as e:
        return _invalid(e)
    except KeyError as e:
        return _field_error("selected_id", str(e).strip("'\""))
    if body.format == "md":
        return PlainTextResponse(
            text,
            media_type="text/markdown",
            headers={"Content-Disposition": "attachment; filename=mechdesign-report.md"},
        )
    return HTMLResponse(text, headers={"Content-Disposition": "attachment; filename=mechdesign-report.html"})


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


def load_dotenv(path: Path | None = None) -> None:
    """Minimal ``.env`` loader (KEY=VALUE lines) for the current directory.

    Variables already present in the environment take precedence.
    """
    path = path or Path.cwd() / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip('"').strip("'")
        if v:
            os.environ.setdefault(k.strip(), v)


def serve(host: str | None = None, port: int | None = None, open_browser: bool = False) -> None:
    import uvicorn

    load_dotenv()
    host = host or os.environ.get("MECHDESIGN_HOST", "127.0.0.1")
    port = port or int(os.environ.get("MECHDESIGN_PORT", "8000"))
    if open_browser:
        import threading
        import webbrowser

        shown = "127.0.0.1" if host in ("0.0.0.0", "::") else host
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{shown}:{port}")).start()
    uvicorn.run(app, host=host, port=port)
