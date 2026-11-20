# User guide

- [Web application](#web-application)
- [The assistant](#the-assistant)
- [Reports](#reports)
- [Command line](#command-line)
- [Configuration format](#configuration-format)

## Web application

Start the app by double-clicking `start.bat` (Windows) or running `python3 start.py` (macOS/Linux); if you installed
the package yourself, run `mechdesign serve --open`. The app runs at <http://127.0.0.1:8000>.
A labelled example configuration is loaded and calculated on start-up.

### Inputs (left panel)

| Group | Fields | Notes |
|---|---|---|
| Geometry | L, b, h [mm] | b is out of the bending plane; h is in the load direction. |
| Material | preset, name, E [GPa], ρ [kg/m³] | Pick a preset or type your own values. The preset selector switches to *Custom* when you edit a value. |
| Load & requirements | F [N], allowable tip deflection [mm], optional allowable stress [MPa], optional max h/b | F is a magnitude; its direction is fixed (−h). Zero is allowed but flagged. |
| Search space | b and h: min, max, step [mm] | L, material and load stay fixed during the search. The number of candidates is shown live (limit 40 000). |

**Calculate & compare** validates everything and runs the search. Invalid inputs are listed with what to fix, and the
fields are highlighted. Examples of what is caught:

- negative or zero dimensions, and a zero step;
- max below min;
- non-numeric text;
- E entered in Pa instead of GPa;
- density entered in g/cm³ instead of kg/m³;
- a grid that is too large.

**Save inputs** downloads the current inputs as JSON. **Open inputs…** loads such a file. The format is the same one the
CLI uses (see [Configuration format](#configuration-format)). Fields missing from a loaded file stay blank and are
reported; they are never filled in from the example.

### Results (centre panel)

- **Numbers** for the current design or the selected candidate:
  - b, h, L and I;
  - mass, actual tip deflection and maximum bending stress;
  - the change in mass relative to the current design;
  - feasibility.
- **Checks**: one line per constraint, with the utilisation (value ÷ limit).
- **Warnings** when model assumptions are stretched: L/h < 10 (shear deformation), h/b > 4 (lateral-torsional buckling
  not checked), δ/L > 0.05 (small-deflection theory), and zero load.
- **3D view**: drag to rotate, scroll to zoom, double-click to reset. It shows:
  - the hatched block, which is the ideal clamp;
  - the red arrow, which is the load F and its direction;
  - the dashed outline, which is the undeformed beam;
  - the orange body, which is the deformed shape.

  The deformation is **magnified**. The factor is shown in the box below the view; you can edit it or press **Auto**.
  The note under the view always gives the **actual predicted tip deflection** in mm. If the 3D library cannot be
  loaded (offline), a message replaces the view and everything else keeps working.
- **Mass vs tip deflection**: one point per sampled candidate.
  - Green points are feasible.
  - Grey points fail the deflection limit.
  - Orange points fail only the stress or aspect-ratio limit.
  - The blue diamond is the current design, and the ring marks the selected candidate.
  - The dashed red line is the deflection limit.

  Hover a point for its values and click it to select it.
- **Candidate comparison**: *Feasible, ranked by mass* or *All candidates*. Click a header to sort, and click or press
  Enter on a row to select it. The *Why feasible / rejected* column states the governing checks. ⚠ marks a row with
  validity warnings (hover the reason to read them). When nothing is feasible, the closest candidates are listed and
  labelled as infeasible.
- **Use as current design** copies the selected b and h into the inputs.
- **Cross-check (FE)** compares the selected design with three independent numerical solvers (see [validation](validation.md)).

## The assistant

Type a request or click one of the example chips. The assistant **never changes the inputs on its own**:

1. It shows a summary of what it understood, and a table of proposed values. Each value is tagged:
   - *stated by you*: the number, or a unit conversion of it, appears in your message;
   - *derived from current design*: copied from or computed from current values. For example, "without increasing
     width" sets b max to the current width, and "30 % stiffer" sets the deflection limit to F ÷ (1.3 × current stiffness);
   - *suggestion – confirm*: anything else, such as material preset values.
2. **Missing requirements** appear as empty required fields. *Apply & recalculate* stays disabled until you fill them
   in. Vague goals ("more stable", "sturdier", "better") always ask for a load and an acceptable deflection.
3. It lists the requirements that will be used unchanged from the form, so nothing is assumed silently.
4. After you apply, the engine recalculates and an explanation is added. Every number in the explanation is inserted
   from engine results. If the model writes a number that cannot be traced to the results, it is flagged.

Without an API key, a small rule-based parser is used and labelled as such. It recognises:

- goals: lighter, stiffer, compare, lower stress;
- numbers with units: mm, cm, m, N, kN, kg, g, MPa, GPa, %, ×;
- "without increasing / keep the same" width or height;
- material names (PLA, PETG, ABS, aluminium, steel);
- aspect-ratio limits.

See [examples/example_requests.md](../examples/example_requests.md).

## Reports

**Export report (HTML / Markdown)** in the header, or `mechdesign report`. A report contains:

1. Inputs with units, and the search ranges.
2. Model formulas, assumptions and limitations.
3. Current design results and checks.
4. Search summary, ranked feasible candidates (or the closest infeasible ones), with reasons.
5. The selected candidate, if any.
6. Validation information: a live FE cross-check of the reported design and the result of the documented suite.
7. A narrative explanation (numbers taken from engine results).

A sample is in [examples/sample_report.md](../examples/sample_report.md).

## Command line

```
mechdesign serve [--host H] [--port P] [--open]
mechdesign example [-o FILE]
mechdesign run CONFIG [--top N] [--json]
mechdesign report CONFIG [-o FILE.html|FILE.md] [--format html|md] [--select ID]
mechdesign validate [--out DIR]
mechdesign --version
```

- `CONFIG` is a JSON file, or `-` for stdin.
- Candidate ids look like `b6_h10` (b = 6 mm, h = 10 mm). They appear in `run` output and in the web table.
- Exit codes: `0` success; `2` invalid configuration (each problem is printed to stderr); `1` failing validation checks.
- `python -m mechdesign` without arguments starts the web app.

## Configuration format

All values are in display units. This is the JSON that **Save inputs**, `mechdesign example` and the HTTP API use.

```json
{
  "length_mm": 80.0,
  "width_mm": 20.0,
  "height_mm": 6.0,
  "material": { "name": "PLA (nominal bulk values)", "E_GPa": 3.5, "density_kg_m3": 1240.0 },
  "load_N": 5.0,
  "allowable_deflection_mm": 0.5,
  "allowable_stress_MPa": 20.0,
  "max_aspect_ratio": null,
  "search": {
    "b_min_mm": 5.0, "b_max_mm": 30.0, "b_step_mm": 1.0,
    "h_min_mm": 3.0, "h_max_mm": 12.0, "h_step_mm": 0.5
  }
}
```

| Key | Required | Meaning |
|---|---|---|
| `length_mm`, `width_mm`, `height_mm` | yes | Current design geometry, > 0 |
| `material.E_GPa` | yes | Young's modulus, 0.001–2000 GPa |
| `material.density_kg_m3` | yes | Density, 10–25 000 kg/m³ |
| `material.name` | no | Label only |
| `load_N` | yes | Tip load magnitude, ≥ 0 |
| `allowable_deflection_mm` | yes | > 0 |
| `allowable_stress_MPa` | no | `null` = not checked |
| `max_aspect_ratio` | no | Upper bound on h/b; `null` = not checked |
| `search.*` | yes | min > 0, max ≥ min, step > 0; ≤ 400 values per axis and ≤ 40 000 candidates |
| `_label` | no | Free-text note shown in reports |
