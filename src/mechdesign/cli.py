"""Command-line interface.

    mechdesign serve [--host H] [--port P] [--open]
    mechdesign example [-o config.json]
    mechdesign run CONFIG [--top N] [--json]
    mechdesign report CONFIG [-o report.html|report.md] [--select ID]
    mechdesign validate [--out DIR]

``python -m mechdesign`` with no arguments starts the web app.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from . import mechanics as M


def _load_config(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    p = Path(path)
    if not p.is_file():
        raise SystemExit(f"error: config file not found: {path}")
    try:
        cfg = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"error: {path} is not valid JSON ({e})") from e
    if not isinstance(cfg, dict):
        raise SystemExit(f"error: {path} must contain a JSON object")
    return cfg


def _print_input_errors(e: M.InputError) -> int:
    print("Invalid configuration - please correct the following:", file=sys.stderr)
    for err in e.errors:
        print(f"  {err.field}: {err.message}", file=sys.stderr)
    return 2


def _fmt(v: float, sig: int = 4) -> str:
    return f"{v:.{sig}g}"


def cmd_serve(a: argparse.Namespace) -> int:
    from .server import serve

    serve(a.host, a.port, a.open)
    return 0


def cmd_example(a: argparse.Namespace) -> int:
    text = json.dumps(M.EXAMPLE_CONFIG, indent=2) + "\n"
    if a.output:
        Path(a.output).write_text(text, encoding="utf-8")
        print(f"Wrote example configuration to {a.output}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_run(a: argparse.Namespace) -> int:
    cfg = _load_config(a.config)
    try:
        out = M.run_problem(cfg, top_n=a.top)
    except M.InputError as e:
        return _print_input_errors(e)
    if a.json:
        sys.stdout.write(json.dumps({k: v for k, v in out.items() if k != "candidates"}, indent=1) + "\n")
        return 0

    c = out["config"]
    cur = out["current"]
    print(f"MechDesign Agent {__version__} - rectangular cantilever, Euler-Bernoulli beam theory")
    print(
        f"L = {_fmt(c['length_mm'])} mm, material {out['material_name']} (E = {_fmt(c['material']['E_GPa'])} GPa), "
        f"F = {_fmt(c['load_N'])} N, allowable deflection {_fmt(c['allowable_deflection_mm'])} mm"
        + (
            f", allowable stress {_fmt(c['allowable_stress_MPa'])} MPa"
            if c.get("allowable_stress_MPa") is not None
            else ""
        )
    )
    print()
    print(
        f"Current design b = {_fmt(cur['b_mm'])} mm, h = {_fmt(cur['h_mm'])} mm: mass {_fmt(cur['mass_g'])} g, "
        f"tip deflection {_fmt(cur['deflection_mm'])} mm, max stress {_fmt(cur['stress_MPa'])} MPa -> "
        f"{'FEASIBLE' if cur['feasible'] else 'NOT FEASIBLE'}"
    )
    for chk in cur["checks"]:
        print(f"  [{'pass' if chk['passed'] else 'FAIL'}] {chk['text']}")
    for w in cur["warnings"]:
        print(f"  [warn] {w}")
    print()
    print(out["statement"])
    rows = out["top"] if out["top"] else out["nearest_infeasible"]
    if rows:
        print()
        print(
            "Feasible candidates ranked by mass:"
            if out["top"]
            else "Closest INFEASIBLE candidates (constraints not relaxed):"
        )
        hdr = f"{'rank':>4} {'b [mm]':>8} {'h [mm]':>8} {'mass [g]':>9} {'vs cur':>8} {'defl [mm]':>10} {'stress [MPa]':>12}  id"
        print(hdr)
        print("-" * len(hdr))
        for r in rows:
            print(
                f"{r['rank'] or '-':>4} {_fmt(r['b_mm']):>8} {_fmt(r['h_mm']):>8} {_fmt(r['mass_g']):>9} "
                f"{r['mass_change_vs_current_pct']:>+7.1f}% {_fmt(r['deflection_mm']):>10} {_fmt(r['stress_MPa']):>12}  {r['id']}"
            )
    return 0


def cmd_report(a: argparse.Namespace) -> int:
    from .report import generate_report

    cfg = _load_config(a.config)
    fmt = a.format or ("md" if a.output and a.output.lower().endswith(".md") else "html")
    try:
        text = generate_report(cfg, a.select, fmt, include_explanation=True)
    except M.InputError as e:
        return _print_input_errors(e)
    except KeyError as e:
        print(f"error: {e.args[0]}", file=sys.stderr)
        return 2
    if a.output:
        Path(a.output).write_text(text, encoding="utf-8")
        print(f"Wrote {fmt.upper()} report to {a.output}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_validate(a: argparse.Namespace) -> int:
    from .validation import run_suite, write_outputs

    res = run_suite()
    for c in res["checks"]:
        print(
            f"[{'PASS' if c['pass'] else 'FAIL'}] {c['case']} {c['check']}: {c['rel_diff']:+.3e} (tol {c['tolerance']:g})"
        )
    s = res["summary"]
    print(
        f"\n{s['n_pass']}/{s['n_checks']} checks passed"
        + ("" if s["anastruct_included"] else " (anaStruct not installed: its checks were skipped)")
    )
    if a.out:
        j, m = write_outputs(res, Path(a.out))
        print(f"Wrote {j} and {m}")
    return 0 if s["n_pass"] == s["n_checks"] else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mechdesign",
        description="MechDesign Agent: explore rectangular cantilever sensor-mount designs.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("serve", help="start the web application")
    s.add_argument("--host", help="bind address (default 127.0.0.1 or $MECHDESIGN_HOST)")
    s.add_argument("--port", type=int, help="port (default 8000 or $MECHDESIGN_PORT)")
    s.add_argument("--open", action="store_true", help="open the app in the default browser")
    s.set_defaults(func=cmd_serve)

    s = sub.add_parser("example", help="print the labelled example configuration (JSON)")
    s.add_argument("-o", "--output", help="write to this file instead of stdout")
    s.set_defaults(func=cmd_example)

    s = sub.add_parser("run", help="evaluate a configuration and rank candidates")
    s.add_argument("config", help="configuration JSON file ('-' for stdin)")
    s.add_argument("--top", type=int, default=10, help="number of ranked candidates to show (default 10)")
    s.add_argument("--json", action="store_true", help="machine-readable output (without the full candidate list)")
    s.set_defaults(func=cmd_run)

    s = sub.add_parser("report", help="write a calculation report (HTML or Markdown)")
    s.add_argument("config", help="configuration JSON file ('-' for stdin)")
    s.add_argument("-o", "--output", help="output file (.html or .md); stdout if omitted")
    s.add_argument("--format", choices=["html", "md"], help="override the format inferred from --output")
    s.add_argument("--select", metavar="ID", help="candidate id to report in detail, e.g. b6_h10")
    s.set_defaults(func=cmd_report)

    s = sub.add_parser("validate", help="run the documented FE cross-check suite")
    s.add_argument("--out", metavar="DIR", help="also write results.json and results.md to DIR")
    s.set_defaults(func=cmd_validate)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
