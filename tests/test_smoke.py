"""Quick sanity checks: python -m pytest tests/"""
import numpy as np
from gridfail.frequency import FreqSystem, GenLoss, simulate, rocof_initial
from gridfail.cascade import load_case39, cascade
from gridfail.voltage import pmax


def test_rocof_matches_swing_equation():
    s = FreqSystem(demand_mw=30000, ek_mws=120000, reserve_mw=0, load_damping=0,
                   losses=[GenLoss(0, 1200)])
    r = simulate(s, t_end=0.5, dt=0.001)
    slope = (r["f"][100] - r["f"][0]) / 0.1
    assert abs(slope - rocof_initial(1200, 120000)) < 0.01


def test_intact_case39_has_no_overload_at_base():
    s = load_case39(1.0)
    r = cascade(s, [], trip_margin=1.0)
    assert r["load_lost_mw"] == 0 and r["n_tripped"] == 0


def test_doubling_reactance_halves_pmax():
    assert abs(pmax(0.6, 0.2) / pmax(0.3, 0.2) - 0.5) < 0.01
