# Test results

Recorded 2026-11-20 on Windows 11 (build 10.0.26200), Python 3.10.18, with all optional extras installed and `MECHDESIGN_DISABLE_LLM=1`. CI re-runs the suite on Linux, Windows and macOS.

**106 passed in 10.74s** · line+branch coverage **89%** · `mechdesign validate`: **36/36** cross-checks passed.

Also checked by hand: the built wheel installed into a clean environment (Python 3.10, `[validation]` extra only), running the tests shipped in the source package: 100 passed, 6 skipped (the launcher tests need the repository checkout); `mechdesign validate` 36/36. Earlier, the wheel on Python 3.13 with no optional extras: 96 passed, 4 skipped (anaStruct not installed), 24/24 validation checks.

Reproduce with:

```bash
pytest -v --cov
```

| Test module | Tests | What it covers |
|---|---|---|
| `tests/test_api.py` | 15 | HTTP endpoints, 422 errors, report download, .env loading |
| `tests/test_cli.py` | 12 | CLI commands, exit codes, report and validation outputs |
| `tests/test_examples.py` | 7 | every shipped example configuration runs and behaves as labelled |
| `tests/test_fem_crosscheck.py` | 16 | independent solvers: in-house Hermite FE, anaStruct, Q8 continuum vs Timoshenko, shear trend |
| `tests/test_language.py` | 11 | rule-based parser on the example requests, missing-requirement gating, provenance guard, explanation number checks |
| `tests/test_launcher.py` | 6 | one-step launcher: which extras it installs (Windows path-length rule), skipping pip when up to date, reinstalling after the folder moves, refusing a broken .venv |
| `tests/test_llm_path.py` | 4 | LLM orchestration with the API mocked: guard on LLM output, transparent fallback, placeholder filling |
| `tests/test_mechanics.py` | 35 | formulas against hand calculations, unit conversions, scaling laws (L³, 1/h³, …), zero load, invalid inputs, constraint filtering, ranking, no-feasible case |

<details><summary>Full list of test cases</summary>

```
tests/test_api.py::test_status_and_example PASSED
tests/test_api.py::test_run_example PASSED
tests/test_api.py::test_run_invalid_returns_422_with_fields PASSED
tests/test_api.py::test_interpret_and_apply_cycle PASSED
tests/test_api.py::test_explain_and_crosscheck PASSED
tests/test_api.py::test_report[md-# MechDesign Agent - Calculation Report] PASSED
tests/test_api.py::test_report[html-<table>] PASSED
tests/test_api.py::test_frontend_served PASSED
tests/test_api.py::test_health PASSED
tests/test_api.py::test_crosscheck_rejects_bad_poisson_and_dimensions PASSED
tests/test_api.py::test_report_unknown_candidate_is_422 PASSED
tests/test_api.py::test_report_rejects_unknown_format PASSED
tests/test_api.py::test_explain_invalid_config_is_422 PASSED
tests/test_api.py::test_interpret_with_invalid_form_still_answers PASSED
tests/test_api.py::test_load_dotenv PASSED
tests/test_cli.py::test_version PASSED
tests/test_cli.py::test_no_command_prints_help PASSED
tests/test_cli.py::test_example_roundtrip PASSED
tests/test_cli.py::test_run_text PASSED
tests/test_cli.py::test_run_json PASSED
tests/test_cli.py::test_run_invalid_config_exit_code PASSED
tests/test_cli.py::test_run_missing_file PASSED
tests/test_cli.py::test_run_not_json PASSED
tests/test_cli.py::test_report[r.md-# MechDesign Agent - Calculation Report] PASSED
tests/test_cli.py::test_report[r.html-<!doctype html>] PASSED
tests/test_cli.py::test_report_unknown_candidate PASSED
tests/test_cli.py::test_validate_writes_outputs PASSED
tests/test_examples.py::test_examples_exist PASSED
tests/test_examples.py::test_example_runs[aluminium_bracket] PASSED
tests/test_examples.py::test_example_runs[example_config] PASSED
tests/test_examples.py::test_example_runs[no_feasible_design] PASSED
tests/test_examples.py::test_example_runs[steel_textbook] PASSED
tests/test_examples.py::test_example_config_matches_builtin PASSED
tests/test_examples.py::test_steel_textbook_values PASSED
tests/test_fem_crosscheck.py::test_inhouse_hermite_fe_matches[0.08-0.02-0.006-3500000000.0-5.0] PASSED
tests/test_fem_crosscheck.py::test_inhouse_hermite_fe_matches[0.15-0.01-0.004-2100000000.0-2.0] PASSED
tests/test_fem_crosscheck.py::test_inhouse_hermite_fe_matches[0.1-0.01-0.01-200000000000.0-100.0] PASSED
tests/test_fem_crosscheck.py::test_inhouse_hermite_fe_matches[0.03-0.02-0.01-68900000000.0-50.0] PASSED
tests/test_fem_crosscheck.py::test_anastruct_matches[0.08-0.02-0.006-3500000000.0-5.0] PASSED
tests/test_fem_crosscheck.py::test_anastruct_matches[0.15-0.01-0.004-2100000000.0-2.0] PASSED
tests/test_fem_crosscheck.py::test_anastruct_matches[0.1-0.01-0.01-200000000000.0-100.0] PASSED
tests/test_fem_crosscheck.py::test_anastruct_matches[0.03-0.02-0.01-68900000000.0-50.0] PASSED
tests/test_fem_crosscheck.py::test_plane_stress_continuum_vs_timoshenko[0.08-0.02-0.006-3500000000.0-5.0] PASSED
tests/test_fem_crosscheck.py::test_plane_stress_continuum_vs_timoshenko[0.15-0.01-0.004-2100000000.0-2.0] PASSED
tests/test_fem_crosscheck.py::test_plane_stress_continuum_vs_timoshenko[0.1-0.01-0.01-200000000000.0-100.0] PASSED
tests/test_fem_crosscheck.py::test_plane_stress_continuum_vs_timoshenko[0.03-0.02-0.01-68900000000.0-50.0] PASSED
tests/test_fem_crosscheck.py::test_shear_effect_grows_for_stubby_beams PASSED
tests/test_fem_crosscheck.py::test_midspan_stress_from_continuum PASSED
tests/test_fem_crosscheck.py::test_crosscheck_report_structure PASSED
tests/test_fem_crosscheck.py::test_crosscheck_zero_load PASSED
tests/test_language.py::test_lighter_uses_form_requirements_explicitly PASSED
tests/test_language.py::test_stiffer_without_wider_needs_target PASSED
tests/test_language.py::test_compare_with_deflection_limit PASSED
tests/test_language.py::test_vague_request_requires_load_and_deformation PASSED
tests/test_language.py::test_units_and_relative_stiffness PASSED
tests/test_language.py::test_unit_conversion_cm_and_kn PASSED
tests/test_language.py::test_unrecognised_request_does_not_guess PASSED
tests/test_language.py::test_guard_downgrades_invented_numbers PASSED
tests/test_language.py::test_explanation_numbers_come_from_engine PASSED
tests/test_language.py::test_explanation_flags_untraceable_numbers PASSED
tests/test_language.py::test_no_feasible_explanation PASSED
tests/test_launcher.py::test_short_windows_path_installs_all_extras PASSED
tests/test_launcher.py::test_deep_windows_path_skips_llm_extra_and_says_why PASSED
tests/test_launcher.py::test_deep_windows_path_is_fine_with_long_paths_enabled PASSED
tests/test_launcher.py::test_path_length_is_irrelevant_off_windows PASSED
tests/test_launcher.py::test_install_runs_pip_only_when_needed PASSED
tests/test_launcher.py::test_broken_venv_is_reported_not_used PASSED
tests/test_llm_path.py::test_llm_interpretation_is_guarded PASSED
tests/test_llm_path.py::test_llm_failure_falls_back_transparently PASSED
tests/test_llm_path.py::test_llm_explanation_placeholders_and_number_check PASSED
tests/test_llm_path.py::test_no_key_means_disabled PASSED
tests/test_mechanics.py::test_unit_conversions_roundtrip PASSED
tests/test_mechanics.py::test_reference_case_hand_calculation PASSED
tests/test_mechanics.py::test_steel_reference_case PASSED
tests/test_mechanics.py::test_deflection_curve_matches_tip_and_root PASSED
tests/test_mechanics.py::test_deflection_scales_with_L_cubed[0.5] PASSED
tests/test_mechanics.py::test_deflection_scales_with_L_cubed[2.0] PASSED
tests/test_mechanics.py::test_deflection_scales_with_L_cubed[3.0] PASSED
tests/test_mechanics.py::test_deflection_scales_with_inverse_h_cubed[0.5] PASSED
tests/test_mechanics.py::test_deflection_scales_with_inverse_h_cubed[2.0] PASSED
tests/test_mechanics.py::test_deflection_scales_with_inverse_h_cubed[1.7] PASSED
tests/test_mechanics.py::test_other_scalings PASSED
tests/test_mechanics.py::test_zero_load_gives_zero_response_and_warning PASSED
tests/test_mechanics.py::test_invalid_design_rejected[L-0.0] PASSED
tests/test_mechanics.py::test_invalid_design_rejected[L--1.0] PASSED
tests/test_mechanics.py::test_invalid_design_rejected[b-0.0] PASSED
tests/test_mechanics.py::test_invalid_design_rejected[h--0.001] PASSED
tests/test_mechanics.py::test_invalid_design_rejected[E-0.0] PASSED
tests/test_mechanics.py::test_invalid_design_rejected[rho--5.0] PASSED
tests/test_mechanics.py::test_invalid_design_rejected[F--1.0] PASSED
tests/test_mechanics.py::test_invalid_design_rejected[L-nan] PASSED
tests/test_mechanics.py::test_invalid_design_rejected[E-inf] PASSED
tests/test_mechanics.py::test_invalid_config_lists_every_problem PASSED
tests/test_mechanics.py::test_missing_key_reported PASSED
tests/test_mechanics.py::test_unit_plausibility_checks PASSED
tests/test_mechanics.py::test_grid_too_large_rejected PASSED
tests/test_mechanics.py::test_optional_stress_limit_can_be_disabled PASSED
tests/test_mechanics.py::test_parse_config_converts_to_si PASSED
tests/test_mechanics.py::test_grid_values_inclusive_and_float_safe PASSED
tests/test_mechanics.py::test_constraint_filtering_matches_bruteforce PASSED
tests/test_mechanics.py::test_ranking_by_mass_and_all_feasible_satisfy_limits PASSED
tests/test_mechanics.py::test_stress_constraint_filters PASSED
tests/test_mechanics.py::test_aspect_ratio_constraint_filters PASSED
tests/test_mechanics.py::test_no_feasible_design_reported_without_relaxing PASSED
tests/test_mechanics.py::test_current_design_status_example PASSED
tests/test_mechanics.py::test_validity_warnings PASSED
```

</details>
