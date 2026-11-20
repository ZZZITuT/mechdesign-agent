# Architecture

```
Browser (src/mechdesign/web/)          Python package (src/mechdesign/)
-----------------------------          ---------------------------------------------------------
index.html / app.js  ── JSON/HTTP ──▶  server.py  (FastAPI, thin: validation errors -> HTTP 422)
viewer3d.js (Three.js, lazy-loaded)       │
scatter.js (canvas)                       ├─▶ mechanics.py   deterministic engine (SI internally)
                                          │      └─ units.py
Terminal                                  ├─▶ crosscheck.py ─▶ fem.py (independent solvers)
mechdesign CLI  ── cli.py ───────────────▶├─▶ validation.py  documented cross-check suite
                                          ├─▶ report.py      Markdown / HTML report
                                          └─▶ language/service.py
                                                 ├─ llm.py          (Claude, server-side key)
                                                 ├─ rule_parser.py  (fallback, not an LLM)
                                                 └─ schema.py       (shared proposal schema)
```

## Separation of responsibilities

| Layer | Does | Does not |
|---|---|---|
| `mechanics.py` | Validates inputs, converts units, evaluates I, m, δ, σ, checks constraints, runs the grid search, ranks, and writes the feasible/rejected reasons. | Import anything from the UI, server or language layer. |
| `language/` | Turns text into a *proposal* (field, value, source, note), lists missing requirements, writes prose. | Compute mechanics results. The only arithmetic it does is unit conversion of stated numbers and the stated relative-stiffness ratio, using the engine's current results. Every such value is labelled "derived" and shown for review. |
| `server.py`, `cli.py` | Move JSON or files between the user and the modules. The server keeps API credentials server-side. | Hold any engineering logic. |
| `web/` (in the package) | Displays engine output and collects inputs. The 3D shape uses the normalised deflection curve returned by the engine, scaled by the engine's tip deflection. | Calculate any engineering result. |

## Key decisions

- **Installable `src/` package.** The web assets ship inside the wheel (`mechdesign/web/`), so `pip install` gives a
  working app with no front-end build step. The CLI and the web UI share the same functions (`run_problem`,
  `generate_report`, `run_suite`).
- **Python + FastAPI + plain JS.** NumPy/SciPy make the engine and the FE cross-checks short and
  testable. There is no front-end build step, so reproducing the app needs only `pip install` and a browser.
- **SI internally, display units at the edges.** `parse_config()` is the only place where display
  units are converted to SI, and `evaluation_to_display()` the only place where they are converted back.
  Both are covered by tests.
- **Vectorised search, scalar checks.** The grid is evaluated with NumPy. Each candidate's
  reason text is then produced by the same scalar `evaluate()` used for the current design, and a
  test checks the vectorised and scalar feasibility agree for every grid point.
- **Grid generation** uses an integer count (`floor((max-min)/step + 1e-9) + 1`) and rounds to
  12 decimals, so 0.1-type steps don't drop the end point or create values like 0.30000000000000004.
  Limits are 400 values per axis and 40 000 candidates.
- **Ranking**: feasible candidates by mass, ties broken by smaller deflection. When none are feasible,
  the five candidates with the lowest worst-case utilisation are shown, labelled as infeasible.
- **No silent requirements.** The interpretation response lists:
  - every changed field, with its source;
  - every missing requirement, which disables *Apply* until it is filled in;
  - every requirement taken unchanged from the form.

  Vague words (stable, sturdy, robust, better…) always trigger a request for a load and an
  acceptable deformation.
- **Provenance guard** (`service.guard_updates`). A value labelled *user_stated* must match a number
  in the message, possibly after a simple unit conversion. A value labelled *derived_from_current* must
  match a current value or the stated stiffness ratio. Anything else is downgraded to
  *assistant_suggestion*, with a note. This applies to LLM output as well as the parser.
- **Explanations use placeholders.** The LLM receives a FACTS table, built from engine output, and must
  refer to numbers as `{{key}}`. The server fills them in. Any digit the model wrote itself is
  compared with FACTS, and if it doesn't match it is flagged in the UI. The no-LLM template uses the
  same mechanism.
- **LLM call**: Anthropic Python SDK, `client.beta.messages.parse` with a Pydantic schema
  (structured output), model `claude-opus-5-5`, effort `low`, server-side refusal fallback
  (`fallbacks="default"`). Errors are mapped to a short message and the app falls back to the parser,
  saying so in the UI.
- **Magnification**: auto-chosen so the displayed tip drop is about 12 % of L, rounded to 1/2/5×10ⁿ.
  The user can edit it. The UI always prints "shown magnified ×N" next to the actual deflection in mm.
- **Offline-tolerant UI.** Three.js is loaded with a dynamic `import()`. If the CDN is unreachable, the 3D panel shows
  a message and the rest of the UI (calculation, plot, table, assistant, reports) keeps working.
- **Reports run the validation suite live.** The suite is deterministic and takes well under a second, so a report
  states the result produced by the code that generated it, instead of a stored file that might be stale. The suite
  result is cached per process.
- **Validation is independent of the closed form.** See [validation.md](validation.md).

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | liveness check (used by the Docker HEALTHCHECK) |
| GET | `/api/status` | LLM enabled? model name |
| GET | `/api/example` | example config, material presets, assumptions, limitations |
| POST | `/api/run` | validate + evaluate current design + grid search |
| POST | `/api/interpret` | text → proposal (never applied server-side) |
| POST | `/api/explain` | explanation of results (LLM or template) with number checks |
| POST | `/api/crosscheck` | FE cross-check of one design |
| POST | `/api/report` | HTML or Markdown report download |

Request and response formats are documented in [api.md](api.md). The configuration JSON format is described in the
[user guide](user-guide.md#configuration-format).
