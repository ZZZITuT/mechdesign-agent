# HTTP API

The web UI is a thin client of this JSON API. When the server is running, interactive OpenAPI documentation
is available at <http://127.0.0.1:8000/docs>.

All request bodies that contain a `config` use the [configuration format](user-guide.md#configuration-format).
An invalid configuration returns **422** with every problem listed:

```json
{ "error": "invalid_input",
  "errors": [ { "field": "length_mm", "message": "Length must be greater than zero (got -5)." },
              { "field": "material.E_GPa", "message": "is required." } ] }
```

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/health` | – | `{"status": "ok", "version": "0.1.0"}` |
| GET | `/api/status` | – | `llm_enabled`, `llm_model`, `fallback_label`, `version` |
| GET | `/api/example` | – | example `config`, `materials` presets, `assumptions`, `limitations` |
| POST | `/api/run` | `{config}` | full evaluation (see below) |
| POST | `/api/interpret` | `{message, config}` | proposal (never applied on the server) |
| POST | `/api/explain` | `{config, message?, selected_id?}` | explanation text and verification info |
| POST | `/api/crosscheck` | `{config, b_mm?, h_mm?, poisson?}` | FE cross-check of one design |
| POST | `/api/report` | `{config, selected_id?, format: "html"\|"md", message?, include_explanation?}` | report file (attachment) |

## `POST /api/run`

```json
{
  "config": { "...": "echo of the input" },
  "material_name": "PLA (nominal bulk values)",
  "current": {
    "b_mm": 20, "h_mm": 6, "L_mm": 80, "I_mm4": 360, "mass_g": 11.904,
    "deflection_mm": 0.6772, "stress_MPa": 3.333, "feasible": false,
    "checks": [ { "name": "tip_deflection", "value": 0.6772, "limit": 0.5, "unit": "mm",
                  "utilisation": 1.354, "passed": false, "text": "Tip deflection 0.677 mm exceeds limit 0.5 mm" } ],
    "warnings": []
  },
  "search": { "n_candidates": 494, "n_b": 26, "n_h": 19, "n_feasible": 256,
              "n_fail_deflection": 238, "n_fail_stress": 18, "n_fail_aspect": 0,
              "fixed": { "L_mm": 80, "E_GPa": 3.5, "density_kg_m3": 1240, "load_N": 5 } },
  "candidates": [ { "id": "b5_h11", "rank": 1, "b_mm": 5, "h_mm": 11, "mass_g": 5.456,
                    "mass_change_vs_current_pct": -54.17, "deflection_mm": 0.4396, "stress_MPa": 3.967,
                    "feasible": true, "reason": "Feasible: ...", "checks": [], "warnings": [] } ],
  "top": [ "...the first ranked feasible candidates..." ],
  "nearest_infeasible": [ "...only when nothing is feasible, each with max_utilisation..." ],
  "statement": "256 of 494 sampled (b, h) combinations satisfy all constraints. ...",
  "deflection_shape": { "xi": [0, 0.025], "v": [0, 0.0009], "formula": "v(x)/v(L) = x^2 (3L - x) / (2 L^3)" }
}
```

(Values are rounded here for readability; the API returns full precision.)

## `POST /api/interpret`

```json
{
  "mode": "rule-based",
  "mode_label": "Rule-based parser (no LLM configured) - limited pattern matching, not a language model",
  "llm_error": null,
  "intent": "increase_stiffness",
  "summary": "Reduce tip deflection (increase bending stiffness), ...",
  "diffs": [ { "field": "search.b_max_mm", "label": "Search b max", "unit": "mm", "old": 30, "new": 20,
               "source": "derived_from_current", "note": "Do not exceed the current width 20 mm" } ],
  "missing": [ { "field": "allowable_deflection_mm", "label": "Allowable tip deflection", "unit": "mm",
                 "question": "How stiff must it be? ...", "current_form_value": 0.5 } ],
  "used_from_form": [ { "field": "load_N", "label": "Tip load F", "unit": "N", "value": 5 } ],
  "clarifications": [],
  "guard_notes": [],
  "proposed_config": { "...": "config with the diffs applied" },
  "ready": false
}
```

`ready` is `false` while `missing` is not empty. Clients must collect those values before running.

## `POST /api/explain`

Returns `text` (numbers already inserted), `facts` (the key → value table the text was built from), `mode` /
`mode_label`, `unknown_placeholders` and `unverified_numbers`. The last two lists should be empty; if they are not,
show them to the user.

## `POST /api/crosscheck`

Returns `closed_form` (`tip_deflection_mm`, `max_stress_MPa`), a list of `rows` (one per solver, with relative
differences, tolerance and `pass` true/false, or `null` if skipped) and a `disclaimer`.
