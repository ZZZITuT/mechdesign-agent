# Example requests

Each request below was run against the example configuration (`example_config.json`) using the
rule-based fallback (no API key). The behaviour shown is asserted by `tests/test_language.py`.

| Request | Interpretation (rule-based) | Ready to run? |
|---|---|---|
| I want this mount to be lighter. | Intent: reduce mass. No changes. It lists the load (5 N), the allowable deflection (0.5 mm) and the stress limit (20 MPa) as taken from the form. | yes |
| Make it stiffer without increasing its width. | `search.b_max_mm` = 20 (derived from the current width). It asks for the allowable deflection and says the current design deflects 0.6772 mm. | **no**: the deflection target is required |
| Compare designs that deflect less than 0.5 mm. | `allowable_deflection_mm` = 0.5 (stated by you). | yes |
| Make it more stable. | Flags "stable" as ambiguous (static stiffness, vibration or tipping). Asks for the load and the acceptable deflection. Proposes no values. | **no** |
| Make it 30% stiffer, keep the height, use aluminium. The sensor weighs 200 g. | Load = 1.96133 N (200 g × 9.80665 m/s², static). The allowable deflection is derived as F ÷ (1.3 × current stiffness 7.383 N/mm). `h` is fixed at 6 mm. Aluminium E and ρ are shown as preset suggestions to confirm. | yes, after review |
| length 12 cm, load 0.01 kN, deflection under 0.2 mm | L = 120 mm, F = 10 N, allowable deflection = 0.2 mm (all stated, with the unit conversions noted). | yes |
| hello there | No goal identified. The parser asks you to rephrase and proposes nothing. | n/a |

The form on the left accepts all of these values directly. The assistant is a convenience layer, not
the only way to use the tool.
