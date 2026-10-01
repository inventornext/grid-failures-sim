"""
Two-bus voltage stability: P-V (nose) curves.

Sending bus at fixed voltage Vs feeds a load P + jQ through reactance X.
Eliminating the angle from Eqs. (2.4)-(2.5) gives a quadratic in Vr^2:

    Vr^4 + (2*Q*X - Vs^2) * Vr^2 + X^2 * (P^2 + Q^2) = 0

The upper root is the normal operating point, the lower root is unstable,
and where they meet is the nose point (maximum loadability).
Everything in per unit.
"""
import numpy as np


def vr_upper(P, Q, X, Vs=1.0):
    """Upper (stable) receiving-end voltage, or NaN beyond the nose."""
    b = 2 * Q * X - Vs ** 2
    c = X ** 2 * (P ** 2 + Q ** 2)
    disc = b ** 2 - 4 * c
    return np.where(disc >= 0, np.sqrt(np.clip((-b + np.sqrt(np.clip(disc, 0, None))) / 2, 0, None)), np.nan)


def vr_lower(P, Q, X, Vs=1.0):
    b = 2 * Q * X - Vs ** 2
    c = X ** 2 * (P ** 2 + Q ** 2)
    disc = b ** 2 - 4 * c
    return np.where(disc >= 0, np.sqrt(np.clip((-b - np.sqrt(np.clip(disc, 0, None))) / 2, 0, None)), np.nan)


def pmax(X, tan_phi, Vs=1.0, q_comp=0.0):
    """Maximum loadability for a load with Q = P*tan_phi - q_comp (closed form via search)."""
    P = np.linspace(0, 5 * Vs ** 2 / X, 20001)
    Q = P * tan_phi - q_comp
    v = vr_upper(P, Q, X, Vs)
    ok = ~np.isnan(v)
    return P[ok].max()


def nose_curve(X, tan_phi, Vs=1.0, q_comp=0.0, n=600):
    """Return P, upper branch, lower branch for plotting a full nose curve."""
    pm = pmax(X, tan_phi, Vs, q_comp)
    P = np.linspace(0, pm, n)
    Q = P * tan_phi - q_comp
    return P, vr_upper(P, Q, X, Vs), vr_lower(P, Q, X, Vs)
