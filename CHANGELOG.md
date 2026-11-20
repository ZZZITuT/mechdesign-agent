# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-20

First public release.

### Added
- Deterministic mechanics engine for a rectangular cantilever:
  - computes second moment of area, mass, tip deflection and maximum bending stress;
  - works in SI internally and shows mm, N, MPa, GPa and g;
  - validates every field and checks that units are plausible.
- Grid search over width b and height h, with L, material and load fixed:
  - checks deflection, optional stress and optional h/b limits;
  - ranks feasible candidates by mass and gives a reason for each feasible or rejected design;
  - reports clearly when nothing is feasible, without relaxing any limit.
- Web application:
  - inputs form with material presets;
  - rotatable 3D view with the fixed end, load arrow, undeformed and magnified deformed shapes, and the actual deflection shown beside them;
  - mass-vs-deflection scatter plot and sortable candidate table;
  - save and open inputs as JSON;
  - works offline apart from the 3D view.
- Language layer:
  - optional Claude interpretation (structured output, server-side key) or a labelled rule-based fallback;
  - proposals must be reviewed before they are applied, and missing requirements block the run;
  - a provenance guard checks where each proposed number came from;
  - explanations take every number from engine results through placeholders.
- Independent numerical cross-checks:
  - in-house Hermite beam FE;
  - anaStruct (optional);
  - in-house 2D plane-stress Q8 continuum FE compared with the Timoshenko estimate;
  - documented suite of 6 cases and 36 checks.
- Calculation report export (HTML and Markdown).
- `mechdesign` command-line interface: `serve`, `example`, `run`, `report`, `validate`.
- One-step launcher (`start.bat` on Windows, `python start.py` elsewhere). It creates `.venv`, installs the app and opens it,
  and on Windows it skips the LLM extra when the folder path is too long for it.
- Wheel and source distribution; the wheel contains the web front end.
- Test suite (pytest), ruff and mypy configuration, GitHub Actions CI, Dockerfile.

[Unreleased]: ../../compare/v0.1.0...HEAD
[0.1.0]: ../../releases/tag/v0.1.0
