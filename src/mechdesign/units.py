"""Unit conversions between display units (mm, N, MPa, GPa, g) and SI.

All mechanics calculations are performed in SI (m, N, Pa, kg). The UI and
reports use practical units; every conversion goes through this module so it
can be tested in one place.
"""

MM_PER_M = 1000.0
STANDARD_GRAVITY = 9.80665  # m/s^2, used only when a user states a load in kg


def mm_to_m(value_mm: float) -> float:
    return value_mm / MM_PER_M


def m_to_mm(value_m: float) -> float:
    return value_m * MM_PER_M


def gpa_to_pa(value_gpa: float) -> float:
    return value_gpa * 1e9


def pa_to_gpa(value_pa: float) -> float:
    return value_pa / 1e9


def mpa_to_pa(value_mpa: float) -> float:
    return value_mpa * 1e6


def pa_to_mpa(value_pa: float) -> float:
    return value_pa / 1e6


def kg_to_g(value_kg: float) -> float:
    return value_kg * 1000.0


def g_per_cm3_to_kg_per_m3(value: float) -> float:
    return value * 1000.0


def m4_to_mm4(value_m4: float) -> float:
    return value_m4 * 1e12


def kg_mass_to_newton(mass_kg: float) -> float:
    """Weight of a mass under standard gravity (static, no dynamic factor)."""
    return mass_kg * STANDARD_GRAVITY
