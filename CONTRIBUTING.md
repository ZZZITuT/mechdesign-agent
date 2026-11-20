# Contributing to MechDesign Agent

Thanks for your interest! Bug reports, documentation fixes, new validation cases and
code changes are all welcome.

## Ground rules

This is an engineering tool, so correctness and traceability come before features.

1. **All numbers come from the mechanics engine.** Do not add calculations to the UI, the
   server or the language layer. New physics goes in `src/mechdesign/mechanics.py`
   (or a new engine module), with tests.
2. **Every new formula needs tests.** Include at least one hand-calculated reference
   value and one scaling or limiting-case test. If you can, add an independent numerical
   cross-check (`fem.py`, `validation.py`). Document its tolerance in `docs/validation.md`.
3. **Never invent requirements.** The language layer may only propose values. A user must
   review them, and missing requirements must block a run.
4. **Never overstate results.** Do not claim global optimality, physical validation, test
   results or material savings that were not measured.
5. **Keep the scope.** Topology optimisation, arbitrary CAD and dynamic simulation are out of scope
   for now. Open an issue to discuss larger changes first.

## Development setup

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python -m pip install -e ".[dev]"
```
(On macOS/Linux use `.venv/bin/...`.)

Run everything CI runs:

```bash
ruff check .
```

```bash
ruff format --check .
```

```bash
mypy
```

```bash
pytest --cov
```

```bash
mechdesign validate
```

Optional: install the git hooks with `pre-commit install` (see `.pre-commit-config.yaml`).

The web UI is plain ES modules in `src/mechdesign/web/`, with no build step. Start the app with
`mechdesign serve` and reload the page after editing JS or CSS. Restart the server after editing Python.

## Pull requests

- Keep each PR focused on one change. Include tests and documentation updates.
- Add an entry under **[Unreleased]** in `CHANGELOG.md`.
- If you change numerical behaviour, run `mechdesign validate --out validation` and commit the
  regenerated `validation/results.*` files.
- Describe how you checked the change (tests, screenshots for UI changes).

## Reporting bugs

Use the issue templates. For wrong numbers, include the configuration JSON (the **Save inputs** button,
or `mechdesign example` as a starting point) and the value you expected, with its source.

## Code of conduct

Participation in this project is governed by the [Code of Conduct](CODE_OF_CONDUCT.md).
