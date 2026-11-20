## Summary

<!-- What does this change and why? Link related issues. -->

## How was it verified?

<!-- Tests added/updated, validation run, screenshots for UI changes. -->

## Checklist

- [ ] `ruff check`, `ruff format --check`, `mypy` and `pytest` pass locally
- [ ] New or changed calculations have tests (reference value and scaling/limit case)
- [ ] If numerical behaviour changed: `mechdesign validate --out validation` was re-run and the results committed
- [ ] Docs updated (`README.md`, `docs/`), and an entry added to `CHANGELOG.md` under *Unreleased*
- [ ] No overstated claims (global optimum, physical validation, material savings)
