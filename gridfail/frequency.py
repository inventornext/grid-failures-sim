"""
Single-area (aggregated) frequency response model.

Implements the swing equation of Chapter 2 in its system-level form:

    df/dt = f0 * (P_m - P_e) / (2 * E_k)

where E_k is the stored kinetic energy of all synchronous machines (MW*s),
P_m is mechanical power (pre-disturbance balance + governor/reserve response
- generation lost) and P_e is demand, including frequency-sensitive load
damping and any demand already disconnected by UFLS / LFDD.

The model is deliberately simple (one bus, one equivalent governor) so that
every mechanism discussed in the book stays visible:
  * inertia sets the initial RoCoF
  * primary reserve arrests the fall (with a lag and a capacity cap)
  * load damping helps a little
  * under-frequency generator trips reinforce the fall (Pakistan 2023)
  * under-frequency load shedding / LFDD acts as the emergency brake (UK 2019)

It is an illustrative teaching model, not a reproduction of any operator's
measured data.
"""
from dataclasses import dataclass, field
import numpy as np


@dataclass
class GenLoss:
    """A scheduled loss of generation (the initiating event(s))."""
    t: float            # time of loss, s
    mw: float           # active power lost, MW
    ek_mws: float = 0.  # kinetic energy lost with it, MW*s (0 for inverter-based)
    label: str = ""


@dataclass
class UFTrip:
    """A generator that trips on its own under-frequency protection."""
    f_trip: float       # Hz threshold
    mw: float
    ek_mws: float = 0.
    delay: float = 0.2  # s, relay + breaker time once threshold is crossed
    label: str = ""


@dataclass
class ShedStage:
    """One stage of under-frequency load shedding (UFLS / LFDD)."""
    f_trip: float
    mw: float
    delay: float = 0.2
    label: str = ""


@dataclass
class FreqSystem:
    demand_mw: float                 # pre-disturbance demand
    ek_mws: float                    # synchronous kinetic energy, MW*s
    f0: float = 50.0
    reserve_mw: float = 1000.0       # primary (frequency containment) reserve cap
    reserve_tc: float = 8.0          # s, first-order lag of reserve delivery
    reserve_full_df: float = 0.5     # Hz deviation at which reserve is fully called
    reserve_deadband: float = 0.015  # Hz
    fast_reserve_mw: float = 0.0     # e.g. batteries: fast, small time constant
    fast_reserve_tc: float = 0.5
    load_damping: float = 0.02       # fraction of demand per Hz (2 %/Hz)
    f_collapse: float = 47.0         # below this the system is declared blacked out
    losses: list = field(default_factory=list)
    uf_trips: list = field(default_factory=list)
    shed_stages: list = field(default_factory=list)


def simulate(sys: FreqSystem, t_end: float = 60.0, dt: float = 0.01):
    """Integrate the aggregated swing equation (explicit Euler, small dt).

    Returns a dict of numpy arrays and an event log.
    """
    n = int(t_end / dt) + 1
    t = np.linspace(0.0, t_end, n)
    f = np.empty(n); f[0] = sys.f0
    p_res = np.zeros(n); p_fast = np.zeros(n)
    lost = np.zeros(n); shed = np.zeros(n); ek = np.zeros(n)

    ek_now = sys.ek_mws
    lost_now = 0.0
    shed_now = 0.0
    pr, pf = 0.0, 0.0
    log = []

    pending_loss = sorted(sys.losses, key=lambda e: e.t)
    uf_state = [dict(ev=e, armed_at=None, done=False) for e in sys.uf_trips]
    sh_state = [dict(ev=e, armed_at=None, done=False) for e in sys.shed_stages]

    for k in range(n):
        tk = t[k]
        fk = f[k]

        # scheduled losses
        while pending_loss and pending_loss[0].t <= tk + 1e-9:
            e = pending_loss.pop(0)
            lost_now += e.mw; ek_now -= e.ek_mws
            log.append((tk, fk, f"LOSS  {e.mw:7.0f} MW  {e.label}"))

        # protection-driven trips / shedding (threshold + definite delay)
        for st, kind in [(s, "uf") for s in uf_state] + [(s, "sh") for s in sh_state]:
            ev = st["ev"]
            if st["done"]:
                continue
            if fk <= ev.f_trip and st["armed_at"] is None:
                st["armed_at"] = tk
            if st["armed_at"] is not None and tk - st["armed_at"] >= ev.delay:
                st["done"] = True
                if kind == "uf":
                    lost_now += ev.mw; ek_now -= ev.ek_mws
                    log.append((tk, fk, f"TRIP  {ev.mw:7.0f} MW  {ev.label} (UF {ev.f_trip} Hz)"))
                else:
                    shed_now += ev.mw
                    log.append((tk, fk, f"SHED  {ev.mw:7.0f} MW  {ev.label} ({ev.f_trip} Hz)"))

        ek_now = max(ek_now, 1.0)
        df = fk - sys.f0

        # primary reserve: proportional to deviation beyond deadband, capped, lagged
        dev = max(0.0, -df - sys.reserve_deadband)
        frac = min(1.0, dev / sys.reserve_full_df)
        pr += dt * (frac * sys.reserve_mw - pr) / sys.reserve_tc
        pf += dt * (frac * sys.fast_reserve_mw - pf) / sys.fast_reserve_tc

        # demand seen by the system (load damping + shed load)
        p_load = (sys.demand_mw - shed_now) * (1 + sys.load_damping * df)
        p_gen = sys.demand_mw - lost_now + pr + pf
        imbalance = p_gen - p_load

        p_res[k], p_fast[k], lost[k], shed[k], ek[k] = pr, pf, lost_now, shed_now, ek_now
        if k + 1 < n:
            f[k + 1] = fk + dt * sys.f0 * imbalance / (2.0 * ek_now)
            if f[k + 1] < sys.f_collapse:
                log.append((t[k + 1], f[k + 1], "BLACKOUT  frequency collapse"))
                f[k + 2:] = np.nan
                for arr in (p_res, p_fast, lost, shed, ek):
                    arr[k + 1:] = arr[k]
                break

    collapsed = any("BLACKOUT" in m for _, _, m in log)
    return dict(t=t, f=f, reserve=p_res, fast=p_fast, lost=lost, shed=shed,
                ek=ek, log=log, collapsed=collapsed)


def rocof_initial(loss_mw: float, ek_mws: float, f0: float = 50.0) -> float:
    """Initial rate of change of frequency (Hz/s) right after a loss."""
    return -f0 * loss_mw / (2.0 * ek_mws)


def print_log(res):
    for tk, fk, msg in res["log"]:
        print(f"t={tk:7.2f}s  f={fk:6.3f} Hz  {msg}")
