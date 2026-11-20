# Examples

All configurations use the [configuration format](../docs/user-guide.md#configuration-format). Open them in the web
app with **Open inputs…** or run them from the command line:

```bash
mechdesign run examples/aluminium_bracket.json --top 5
```

| File | What it shows |
|---|---|
| [example_config.json](example_config.json) | The labelled example loaded at start-up: a PLA mount whose current design fails the 0.5 mm deflection limit, with 256 feasible alternatives in the grid |
| [aluminium_bracket.json](aluminium_bracket.json) | Metal bracket with a stress limit and a maximum aspect ratio h/b ≤ 3 |
| [steel_textbook.json](steel_textbook.json) | Hand-checkable case: δ = 0.2 mm and σ = 60 MPa for the current design |
| [no_feasible_design.json](no_feasible_design.json) | A deflection limit that no sampled design meets: the app says so and lists the closest candidates without relaxing anything |
| [example_requests.md](example_requests.md) | Assistant requests and how the rule-based parser interprets them |
| [sample_report.md](sample_report.md) / [sample_report.html](sample_report.html) | Reports generated with `mechdesign report examples/example_config.json --select b6_h10` |

All values are illustrative. They are not real product specifications or measured data.
