"""Independent numerical cross-checks for the closed-form cantilever model.

Three solvers, none of which evaluates the closed-form deflection formula:

1. ``beam_fe_euler_bernoulli`` - an in-house 1D finite-element model using
   2-node Hermite-cubic Euler-Bernoulli beam elements (standard stiffness
   matrix, e.g. Cook et al., *Concepts and Applications of Finite Element
   Analysis*, 4th ed., Sec. 2.4). The global stiffness matrix is assembled and
   solved numerically; tip deflection and root moment are read from the
   solution. For a tip point load this element is nodally exact, so agreement
   should be at round-off level - this checks implementation consistency
   (units, load placement, boundary condition), not the physics.

2. ``beam_fe_anastruct`` - the open-source anaStruct 2D frame solver
   (https://github.com/ritchie46/anaStruct). Same physics (Euler-Bernoulli
   frame elements) but a completely separate code base.

3. ``plane_stress_q8`` - an in-house 2D plane-stress continuum FE model using
   8-node serendipity quadrilaterals (3x3 Gauss integration). This does NOT
   use beam theory at all; it includes shear deformation and Poisson effects,
   and its clamp (all root nodes fixed) is slightly stiffer than an ideal
   beam clamp. Differences from Euler-Bernoulli quantify model-form error
   (mainly shear deformation for short, deep beams). It is compared with the
   Timoshenko estimate delta_T = F L^3/(3 E I) + F L/(kappa G A).

Numerical agreement between models is not physical validation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla


@dataclass
class FEResult:
    solver: str
    tip_deflection: float  # m, positive in load direction
    root_moment: float | None  # N m
    max_stress: float | None  # Pa (derived from FE root moment where noted)
    notes: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self):
        return asdict(self)


# ---------------------------------------------------------------------------
# 1. In-house Euler-Bernoulli Hermite beam FE
# ---------------------------------------------------------------------------


def hermite_beam_stiffness(EI: float, le: float) -> np.ndarray:
    l = le
    return (
        EI
        / l**3
        * np.array(
            [
                [12.0, 6 * l, -12.0, 6 * l],
                [6 * l, 4 * l * l, -6 * l, 2 * l * l],
                [-12.0, -6 * l, 12.0, -6 * l],
                [6 * l, 2 * l * l, -6 * l, 4 * l * l],
            ]
        )
    )


def beam_fe_euler_bernoulli(L: float, b: float, h: float, E: float, F: float, n_elements: int = 20) -> FEResult:
    I = b * h**3 / 12.0
    EI = E * I
    ne = n_elements
    le = L / ne
    ndof = 2 * (ne + 1)
    K = np.zeros((ndof, ndof))
    ke = hermite_beam_stiffness(EI, le)
    for e in range(ne):
        dofs = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        K[np.ix_(dofs, dofs)] += ke
    f = np.zeros(ndof)
    f[2 * ne] = -F  # load in -y at the tip (v dof of last node)
    free = np.arange(2, ndof)  # clamp: v0 = theta0 = 0
    u = np.zeros(ndof)
    u[free] = np.linalg.solve(K[np.ix_(free, free)], f[free])
    # Root reaction moment from the first element's end forces.
    fe = ke @ u[0:4]
    M_root = abs(fe[1])
    sigma = M_root * (h / 2.0) / I
    v_nodes = -u[0::2]
    return FEResult(
        solver=f"In-house Euler-Bernoulli FE ({ne} Hermite elements)",
        tip_deflection=float(-u[2 * ne]),
        root_moment=float(M_root),
        max_stress=float(sigma),
        notes="Root stress = FE root moment x (h/2) / I.",
        extra={"x": list(np.linspace(0, L, ne + 1)), "v": list(v_nodes)},
    )


# ---------------------------------------------------------------------------
# 2. anaStruct (open source)
# ---------------------------------------------------------------------------


def anastruct_available() -> bool:
    try:
        import anastruct  # noqa: F401

        return True
    except Exception:
        return False


def beam_fe_anastruct(L: float, b: float, h: float, E: float, F: float, n_elements: int = 10) -> FEResult:
    from importlib.metadata import version

    from anastruct import SystemElements

    I = b * h**3 / 12.0
    A = b * h
    ss = SystemElements(EA=E * A, EI=E * I)
    xs = np.linspace(0.0, L, n_elements + 1)
    for i in range(n_elements):
        ss.add_element(location=[[xs[i], 0.0], [xs[i + 1], 0.0]])
    ss.add_support_fixed(node_id=1)
    tip = n_elements + 1
    ss.point_load(node_id=tip, Fy=-F)
    ss.solve()
    disp = ss.get_node_displacements(node_id=tip)
    root = ss.get_node_results_system(node_id=1)
    M_root = abs(float(root["Tz"]))
    return FEResult(
        solver=f"anaStruct {version('anastruct')} 2D frame FE ({n_elements} elements)",
        tip_deflection=float(-disp["uy"]),
        root_moment=M_root,
        max_stress=M_root * (h / 2.0) / I,
        notes="Root stress = anaStruct root reaction moment x (h/2) / I.",
    )


# ---------------------------------------------------------------------------
# 3. In-house 2D plane-stress continuum FE (Q8 serendipity)
# ---------------------------------------------------------------------------

_GP = np.array([-np.sqrt(0.6), 0.0, np.sqrt(0.6)])
_GW = np.array([5.0 / 9.0, 8.0 / 9.0, 5.0 / 9.0])
# Natural coordinates of Q8 nodes: corners (CCW) then mid-sides.
_XI = np.array([-1, 1, 1, -1, 0, 1, 0, -1], dtype=float)
_ETA = np.array([-1, -1, 1, 1, -1, 0, 1, 0], dtype=float)


def _q8_shape(xi: float, eta: float):
    N = np.zeros(8)
    dN = np.zeros((2, 8))  # d/dxi, d/deta
    for i in range(4):
        a, c = _XI[i], _ETA[i]
        N[i] = 0.25 * (1 + a * xi) * (1 + c * eta) * (a * xi + c * eta - 1)
        dN[0, i] = 0.25 * a * (1 + c * eta) * (2 * a * xi + c * eta)
        dN[1, i] = 0.25 * c * (1 + a * xi) * (a * xi + 2 * c * eta)
    for i in range(4, 8):
        a, c = _XI[i], _ETA[i]
        if a == 0:  # nodes on eta = +/-1
            N[i] = 0.5 * (1 - xi * xi) * (1 + c * eta)
            dN[0, i] = -xi * (1 + c * eta)
            dN[1, i] = 0.5 * c * (1 - xi * xi)
        else:  # nodes on xi = +/-1
            N[i] = 0.5 * (1 + a * xi) * (1 - eta * eta)
            dN[0, i] = 0.5 * a * (1 - eta * eta)
            dN[1, i] = -eta * (1 + a * xi)
    return N, dN


def plane_stress_q8(
    L: float, b: float, h: float, E: float, F: float, nu: float = 0.3, nx: int | None = None, ny: int = 4
) -> FEResult:
    """2D plane-stress model of the beam's side view (thickness = b).

    Fixed end: every node on x = 0 has ux = uy = 0.
    Load: uniform shear traction F/(b h) on the x = L edge (consistent nodal loads).
    Reported tip deflection: uy at the mid-height node of the loaded edge.
    """
    if nx is None:
        nx = int(np.clip(round(2 * L / h * ny / 2), 20, 300))
    D = E / (1 - nu * nu) * np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])

    gx, gy = 2 * nx + 1, 2 * ny + 1
    node_id = -np.ones((gx, gy), dtype=int)
    coord_list: list[tuple[float, float]] = []
    for i in range(gx):
        for j in range(gy):
            if i % 2 == 1 and j % 2 == 1:
                continue  # Q8 has no centre node
            node_id[i, j] = len(coord_list)
            coord_list.append((i * L / (gx - 1), -h / 2 + j * h / (gy - 1)))
    coords = np.array(coord_list)
    nn = len(coords)
    ndof = 2 * nn

    rows, cols, vals = [], [], []
    elems = []
    for ex in range(nx):
        for ey in range(ny):
            i0, j0 = 2 * ex, 2 * ey
            conn = [
                node_id[i0, j0],
                node_id[i0 + 2, j0],
                node_id[i0 + 2, j0 + 2],
                node_id[i0, j0 + 2],
                node_id[i0 + 1, j0],
                node_id[i0 + 2, j0 + 1],
                node_id[i0 + 1, j0 + 2],
                node_id[i0, j0 + 1],
            ]
            elems.append(conn)
            xy = coords[conn]
            ke = np.zeros((16, 16))
            for a, wa in zip(_GP, _GW, strict=True):
                for c, wc in zip(_GP, _GW, strict=True):
                    _, dN = _q8_shape(a, c)
                    J = dN @ xy
                    detJ = np.linalg.det(J)
                    dNx = np.linalg.solve(J, dN)
                    Bm = np.zeros((3, 16))
                    Bm[0, 0::2] = dNx[0]
                    Bm[1, 1::2] = dNx[1]
                    Bm[2, 0::2] = dNx[1]
                    Bm[2, 1::2] = dNx[0]
                    ke += Bm.T @ D @ Bm * detJ * wa * wc * b
            dofs = np.empty(16, dtype=int)
            dofs[0::2] = 2 * np.array(conn)
            dofs[1::2] = 2 * np.array(conn) + 1
            rows.append(np.repeat(dofs, 16))
            cols.append(np.tile(dofs, 16))
            vals.append(ke.ravel())
    K = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(ndof, ndof))

    f = np.zeros(ndof)
    tau = F / (b * h)
    le = h / ny
    for ey in range(ny):
        n0, nm, n1 = node_id[gx - 1, 2 * ey], node_id[gx - 1, 2 * ey + 1], node_id[gx - 1, 2 * ey + 2]
        for n, wgt in ((n0, 1 / 6), (nm, 4 / 6), (n1, 1 / 6)):
            f[2 * n + 1] -= wgt * tau * b * le

    fixed = []
    for j in range(gy):
        n = node_id[0, j]
        if n >= 0:
            fixed += [2 * n, 2 * n + 1]
    free = np.setdiff1d(np.arange(ndof), fixed)
    u = np.zeros(ndof)
    u[free] = spla.spsolve(K[free][:, free].tocsc(), f[free])

    tip_mid = node_id[gx - 1, ny]  # gy = 2ny+1, middle index = ny
    delta = -u[2 * tip_mid + 1]

    # Bending stress sigma_xx on the top fibre at mid-length (away from the clamp
    # and load-introduction regions), compared with beam theory at that section.
    ex_mid = nx // 2
    conn = elems[ex_mid * ny + (ny - 1)]
    xy = coords[conn]
    _, dN = _q8_shape(-1.0, 1.0)  # left-top corner of that element: x = ex_mid*L/nx
    J = dN @ xy
    dNx = np.linalg.solve(J, dN)
    ue = np.empty(16)
    ue[0::2] = u[2 * np.array(conn)]
    ue[1::2] = u[2 * np.array(conn) + 1]
    Bm = np.zeros((3, 16))
    Bm[0, 0::2] = dNx[0]
    Bm[1, 1::2] = dNx[1]
    Bm[2, 0::2] = dNx[1]
    Bm[2, 1::2] = dNx[0]
    sig = D @ Bm @ ue
    x_s = ex_mid * L / nx

    return FEResult(
        solver=f"In-house 2D plane-stress FE (Q8, {nx}x{ny} elements, nu={nu:g})",
        tip_deflection=float(delta),
        root_moment=None,
        max_stress=None,
        notes=(
            "Continuum model: includes shear deformation and Poisson effects; fully clamped root. "
            "Compare tip deflection with the Timoshenko estimate, not exactly with Euler-Bernoulli."
        ),
        extra={"sigma_xx_top_at_x": float(abs(sig[0])), "x_sample": float(x_s), "dofs": int(ndof), "nx": nx, "ny": ny},
    )


def timoshenko_tip_deflection(L, b, h, E, F, nu=0.3, kappa=5.0 / 6.0) -> float:
    I = b * h**3 / 12.0
    G = E / (2 * (1 + nu))
    return F * L**3 / (3 * E * I) + F * L / (kappa * G * b * h)
