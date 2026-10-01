"""
Quasi-static cascading-failure model on the IEEE 39-bus (New England) system.

This is the classic "overload -> trip -> redistribute" loop of Chapter 2
(Figure 2.3), using a DC power flow:

  1. Solve a DC power flow.
  2. Find branches loaded above their thermal rating.
  3. Trip the most overloaded one (protection acting correctly on its own
     element, "wrong system effect").
  4. If the network splits into islands, rebalance each island:
       - generation is redispatched within its limits,
       - any remaining deficit is shed as load,
       - an island with no generation is blacked out.
  5. Repeat until nothing is overloaded.

DC flow ignores voltage and reactive power, so it captures the thermal
cascade (Northeast 2003, India 2012 corridor overloads) but not voltage
collapse (see voltage.py). Results are illustrative.
"""
import numpy as np
import pandapower.networks as pn


def load_case39(load_scale: float = 1.0, rating_scale: float = 1.0):
    """Build a plain-numpy description of IEEE 39-bus from pandapower data."""
    net = pn.case39()
    nb = len(net.bus)
    zbase = 345.0 ** 2 / net.sn_mva

    br = []
    for i, r in net.line.iterrows():
        x = r.x_ohm_per_km * r.length_km / zbase
        rate = np.sqrt(3) * 345.0 * r.max_i_ka * r.parallel
        br.append(("L", int(r.from_bus), int(r.to_bus), x, rate))
    for i, r in net.trafo.iterrows():
        x = r.vk_percent / 100.0 * net.sn_mva / r.sn_mva
        br.append(("T", int(r.hv_bus), int(r.lv_bus), x, r.sn_mva))

    load = np.zeros(nb)
    for _, r in net.load.iterrows():
        load[int(r.bus)] += r.p_mw * load_scale

    gen_bus, gen_pmax, gen_p0 = [], [], []
    for _, r in net.gen.iterrows():
        gen_bus.append(int(r.bus)); gen_pmax.append(r.max_p_mw); gen_p0.append(r.p_mw)
    slack_p0 = net.load.p_mw.sum() - net.gen.p_mw.sum()   # lossless DC: slack covers the rest
    for _, r in net.ext_grid.iterrows():
        gen_bus.append(int(r.bus)); gen_pmax.append(r.max_p_mw); gen_p0.append(slack_p0)

    names = [f"{k}{a+1}-{b+1}" for (k, a, b, _, _) in br]  # 1-indexed bus names
    return dict(
        nb=nb,
        f=np.array([b[1] for b in br]), t=np.array([b[2] for b in br]),
        x=np.array([b[3] for b in br]), rate=np.array([b[4] for b in br]) * rating_scale,
        kind=[b[0] for b in br], names=names,
        load=load, gen_bus=np.array(gen_bus), gen_pmax=np.array(gen_pmax), gen_p0=np.array(gen_p0),
    )


def _islands(nb, f, t, alive):
    parent = list(range(nb))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i in np.where(alive)[0]:
        ra, rb = find(f[i]), find(t[i])
        if ra != rb:
            parent[ra] = rb
    groups = {}
    for b in range(nb):
        groups.setdefault(find(b), []).append(b)
    return list(groups.values())


def _dispatch(p0, pmax, demand):
    """Share `demand` across units in proportion to their schedule, capped at pmax."""
    p = np.zeros_like(p0, dtype=float)
    free = np.ones(len(p0), dtype=bool)
    rem = demand
    w = np.where(p0 > 0, p0, pmax).astype(float)
    for _ in range(len(p0) + 1):
        if rem <= 1e-9 or not free.any():
            break
        share = rem * w[free] / w[free].sum()
        room = pmax[free] - p[free]
        add = np.minimum(share, room)
        idx = np.where(free)[0]
        p[idx] += add
        rem -= add.sum()
        free[idx[add >= room - 1e-9]] = False
    return p


def dc_flow(sys, alive, load):
    """DC power flow with per-island balancing. Returns flows, served load."""
    nb = sys["nb"]
    flows = np.zeros(len(sys["x"]))
    served = load.copy()
    pinj = np.zeros(nb)

    for isl in _islands(nb, sys["f"], sys["t"], alive):
        isl_set = set(isl)
        gmask = np.array([b in isl_set for b in sys["gen_bus"]])
        dem = load[isl].sum()
        cap = sys["gen_pmax"][gmask].sum()
        if cap <= 0 or dem <= 0:
            served[isl] = 0.0 if cap <= 0 else served[isl]
            continue
        # shed load proportionally if generation is insufficient
        if dem > cap:
            served[isl] = load[isl] * cap / dem
            dem = cap
        # redispatch: scale the original schedule, respecting each unit's limit
        gi = np.where(gmask)[0]
        p = _dispatch(sys["gen_p0"][gi], sys["gen_pmax"][gi], dem)
        for g, pg in zip(gi, p):
            pinj[sys["gen_bus"][g]] += pg
        pinj[isl] -= served[isl]

        if len(isl) == 1:
            continue
        idx = {b: k for k, b in enumerate(isl)}
        m = len(isl)
        B = np.zeros((m, m))
        for i in np.where(alive)[0]:
            a, b = sys["f"][i], sys["t"][i]
            if a in isl_set:
                y = 1.0 / sys["x"][i]
                ia, ib = idx[a], idx[b]
                B[ia, ia] += y; B[ib, ib] += y
                B[ia, ib] -= y; B[ib, ia] -= y
        p = np.array([pinj[b] for b in isl])
        theta = np.zeros(m)
        theta[1:] = np.linalg.solve(B[1:, 1:], p[1:])
        for i in np.where(alive)[0]:
            a, b = sys["f"][i], sys["t"][i]
            if a in isl_set:
                flows[i] = (theta[idx[a]] - theta[idx[b]]) / sys["x"][i]
    return flows, served


def cascade(sys, initial_outages, max_steps=100, trip_margin=1.0, one_at_a_time=True):
    """Run the cascade. Returns a list of steps and the final state."""
    alive = np.ones(len(sys["x"]), dtype=bool)
    for name in initial_outages:
        alive[sys["names"].index(name) if isinstance(name, str) else name] = False

    total = sys["load"].sum()
    steps = []
    flows, served = dc_flow(sys, alive, sys["load"])
    steps.append(dict(step=0, tripped=list(initial_outages), served=served.sum(),
                      max_loading=np.max(np.abs(flows) / sys["rate"])))

    for s in range(1, max_steps + 1):
        loading = np.abs(flows) / sys["rate"]
        loading[~alive] = 0
        over = np.where(loading > trip_margin)[0]
        if len(over) == 0:
            break
        to_trip = [over[np.argmax(loading[over])]] if one_at_a_time else list(over)
        for i in to_trip:
            alive[i] = False
        flows, served = dc_flow(sys, alive, sys["load"])
        steps.append(dict(step=s, tripped=[sys["names"][i] for i in to_trip],
                          trip_loading=[loading[i] for i in to_trip],
                          served=served.sum(),
                          max_loading=np.max(np.where(alive, np.abs(flows) / sys["rate"], 0))))

    return dict(steps=steps, alive=alive, flows=flows, served=served,
                load_lost_mw=total - served.sum(), load_lost_pct=100 * (1 - served.sum() / total),
                n_tripped=int((~alive).sum()) - len(initial_outages))


def n1_screen(sys, **kw):
    """Single-outage screening: cascade outcome for every possible first trip."""
    out = []
    for i, name in enumerate(sys["names"]):
        r = cascade(sys, [name], **kw)
        out.append((name, r["n_tripped"], r["load_lost_mw"], r["load_lost_pct"]))
    return out
