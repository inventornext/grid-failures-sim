"""Build and execute the companion notebooks.  Run from the repo root:

    python tools/build_notebooks.py
"""
import os
import nbformat as nbf
from nbconvert.preprocessors import ExecutePreprocessor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NB_DIR = os.path.join(ROOT, "notebooks")
os.makedirs(NB_DIR, exist_ok=True)
os.makedirs(os.path.join(ROOT, "figures"), exist_ok=True)

SETUP = """import sys, os
sys.path.insert(0, os.path.abspath('..'))
import numpy as np
import matplotlib.pyplot as plt
from gridfail import plotstyle as ps
ps.apply()
FIG = os.path.abspath(os.path.join('..', 'figures'))"""

BOOK = ("*Companion to* **Biggest Power Grid Failures: Engineering Analysis of History's Most "
        "Severe Blackouts, Cascades, and Grid Failures** *by Ganesh Kumar Pandey.*")

DISCLAIMER = ("> **Model note.** This is a simplified teaching model. Parameters are chosen to be "
              "plausible and to reproduce the *shape* of the reported event, not to replicate any "
              "operator's measured data. For the authoritative record, read the official report "
              "cited in the book.")


def nb(cells):
    n = nbf.v4.new_notebook()
    n.cells = [nbf.v4.new_markdown_cell(c[1]) if c[0] == "md" else nbf.v4.new_code_cell(c[1])
               for c in cells]
    n.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    return n


NOTEBOOKS = {}

# ---------------------------------------------------------------------------
NOTEBOOKS["01_inertia_and_rocof.ipynb"] = nb([
    ("md", f"""# 01 · Inertia and the speed of a frequency fall
{BOOK} See **Chapter 2, Sections 2.3 and Figure 2.1**.

When a generator trips, the first thing that resists the frequency fall is not any controller. It is the
kinetic energy stored in every spinning synchronous machine. The system-level swing equation gives the
initial rate of change of frequency (RoCoF):

$$\\frac{{df}}{{dt}}\\Big|_{{t=0^+}} = -\\frac{{f_0\\,\\Delta P}}{{2\\,E_k}}$$

Halve the inertia and the frequency falls twice as fast, leaving half the time for reserves to respond.
This is the core reason high-renewable grids (UK 2019, Iberia 2025) need fast frequency response.

{DISCLAIMER}"""),
    ("code", SETUP),
    ("code", """from gridfail.frequency import FreqSystem, GenLoss, ShedStage, simulate, rocof_initial

DEMAND = 30000     # MW
LOSS = 1500        # MW, sudden generation loss at t = 1 s
H_cases = {'High inertia (H = 6 s, mostly synchronous)': 6.0,
           'Medium (H = 4 s)': 4.0,
           'Low inertia (H = 2 s, high renewables)': 2.0}

fig, ax = plt.subplots()
rows = []
for (label, H), c in zip(H_cases.items(), ps.SERIES):
    ek = H * DEMAND
    s = FreqSystem(demand_mw=DEMAND, ek_mws=ek, reserve_mw=1800, reserve_tc=8,
                   load_damping=0.02, losses=[GenLoss(1.0, LOSS, 0, 'unit trip')])
    r = simulate(s, t_end=30, dt=0.005)
    ax.plot(r['t'], r['f'], color=c, label=label)
    i = np.nanargmin(r['f'])
    rows.append((label, rocof_initial(LOSS, ek), r['f'][i], r['t'][i] - 1.0))

ps.threshold(ax, 48.8, 'typical first UFLS stage, 48.8 Hz')
ax.set_xlabel('Time (s)'); ax.set_ylabel('Frequency (Hz)')
ax.set_title('Same 1,500 MW loss, three levels of inertia')
ax.set_ylim(48.6, 50.1); ax.legend(loc='upper right')
fig.savefig(os.path.join(FIG, '01_inertia_rocof.png'))
plt.show()

print(f"{'Case':48s} {'RoCoF (Hz/s)':>13s} {'Nadir (Hz)':>11s} {'t to nadir (s)':>15s}")
for lab, rocof, nadir, tn in rows:
    print(f"{lab:48s} {rocof:13.3f} {nadir:11.3f} {tn:15.1f}")"""),
    ("md", """**Reading the result.** The reserve is identical in all three cases, yet the low-inertia system falls
fastest and deepest, because the same governor lag now has to fight a steeper slope. The low-inertia case
crosses the first load-shedding threshold; the others do not.

**Try it:** raise `reserve_tc` (slower reserve) or add `fast_reserve_mw=500, fast_reserve_tc=0.5`
(a battery) to the low-inertia case and see how much nadir you buy back."""),
])

# ---------------------------------------------------------------------------
NOTEBOOKS["02_uk_2019_lfdd.ipynb"] = nb([
    ("md", f"""# 02 · UK, 9 August 2019: correlated losses beat an N-1 reserve
{BOOK} See **Chapter 9**.

National Grid ESO held about 1,000 MW of frequency-containment reserve, sized to the single largest
loss. Within about a second of one lightning strike, several *independent* losses stacked up. The loss
sequence below follows the ESO technical report (ref. [19] in the book):

| t (s) | Loss | MW |
|---|---|---|
| 0.0 | Embedded generation (vector shift) | 150 |
| 0.1 | Hornsea 1 offshore wind | 737 |
| 0.6 | Little Barford steam turbine | 244 |
| 1.0 | Embedded generation (RoCoF protection) | 350 |
| ~58 | Little Barford gas turbine 1A | 210 |

LFDD (Low Frequency Demand Disconnection) acts at 48.8 Hz and removed about 931 MW of demand.

{DISCLAIMER}"""),
    ("code", SETUP),
    ("code", """from gridfail.frequency import FreqSystem, GenLoss, ShedStage, simulate, print_log

def uk2019(extra_losses=True, reserve_mw=528, battery_mw=472, lfdd=True):
    losses = [GenLoss(0.0, 150, 0, 'embedded gen, vector shift'),
              GenLoss(0.1, 737, 0, 'Hornsea 1'),
              GenLoss(0.6, 244, 2000, 'Little Barford ST'),
              GenLoss(1.0, 350, 0, 'embedded gen, RoCoF')]
    if extra_losses:
        losses.append(GenLoss(58.0, 210, 1500, 'Little Barford GT1A'))
    s = FreqSystem(demand_mw=29000, ek_mws=210000,
                   reserve_mw=reserve_mw, reserve_tc=8,
                   fast_reserve_mw=battery_mw, fast_reserve_tc=0.8,   # batteries
                   load_damping=0.019, losses=losses,
                   shed_stages=[ShedStage(48.8, 931, 0.1, 'LFDD')] if lfdd else [])
    return simulate(s, t_end=120, dt=0.01)

base = uk2019()
print_log(base)"""),
    ("code", """fig, ax = plt.subplots()
ax.plot(base['t'], base['f'], color=ps.SERIES[0], label='Simulated frequency')
ps.threshold(ax, 48.8, 'LFDD threshold 48.8 Hz')
for tk, fk, msg in base['log']:
    if 'GT1A' in msg:
        ax.annotate('GT1A trips (+210 MW)', xy=(tk, fk), xytext=(tk + 8, fk + 0.3), ha='left',
                    arrowprops=dict(arrowstyle='->', color=ps.TEXT2), color=ps.TEXT2, fontsize=9)
    if 'SHED' in msg:
        ax.annotate('LFDD sheds ~931 MW', xy=(tk, fk), xytext=(tk + 6, fk - 0.12),
                    arrowprops=dict(arrowstyle='->', color=ps.TEXT2), color=ps.TEXT2, fontsize=9)
i = np.argmin(base['f'][:5700])
ax.annotate(f'first nadir {base["f"][i]:.2f} Hz', xy=(base['t'][i], base['f'][i]),
            xytext=(base['t'][i], base['f'][i] + 0.25), ha='center',
            arrowprops=dict(arrowstyle='->', color=ps.TEXT2), color=ps.TEXT2, fontsize=9)
ax.set_xlabel('Time after lightning strike (s)'); ax.set_ylabel('Frequency (Hz)')
ax.set_title('GB, 9 Aug 2019: two-stage fall to the LFDD threshold (model)')
ax.set_ylim(48.5, 50.1)
fig.savefig(os.path.join(FIG, '02_uk2019_frequency.png'))
plt.show()"""),
    ("md", """## What-if: which single change would have avoided LFDD?

Chapter 9 lists the root causes. Here we switch each one off in turn and check whether frequency still
reaches 48.8 Hz."""),
    ("code", """def did_shed(r):
    return any('SHED' in m for _, _, m in r['log'])

scenarios = {
    'As happened': uk2019(),
    'No RoCoF/vector-shift embedded trips (500 MW kept)':
        simulate(FreqSystem(
            demand_mw=29000, ek_mws=210000, reserve_mw=528, reserve_tc=8,
            fast_reserve_mw=472, fast_reserve_tc=0.8, load_damping=0.019,
            losses=[GenLoss(0.1, 737, 0, 'Hornsea 1'), GenLoss(0.6, 244, 2000, 'LB ST'),
                    GenLoss(58.0, 210, 1500, 'LB GT1A')],
            shed_stages=[ShedStage(48.8, 931, 0.1, 'LFDD')]), 120, 0.01),
    'Reserve sized for correlated loss (+700 MW)': uk2019(reserve_mw=1228),
    'No batteries (472 MW replaced by nothing)': uk2019(battery_mw=0),
}

fig, ax = plt.subplots()
for (lab, r), c in zip(scenarios.items(), ps.SERIES):
    ax.plot(r['t'], r['f'], color=c, label=f"{lab}  ->  {'LFDD' if did_shed(r) else 'no LFDD'}")
ps.threshold(ax, 48.8, 'LFDD 48.8 Hz')
ax.set_xlabel('Time (s)'); ax.set_ylabel('Frequency (Hz)')
ax.set_title('Which fix would have kept 1.1 million customers on?')
ax.set_ylim(48.5, 50.1)
ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.16), ncol=2, fontsize=8.5)
fig.savefig(os.path.join(FIG, '02_uk2019_whatif.png'))
plt.show()

for lab, r in scenarios.items():
    print(f"{lab:55s} min f = {np.nanmin(r['f']):.3f} Hz   LFDD: {did_shed(r)}")"""),
    ("md", """**Reading the result.** Keeping the 500 MW of embedded generation online, or holding reserve against a
*correlated* loss, both keep frequency above 48.8 Hz. Removing the batteries makes the first dip far
worse. This is the book's argument in numbers: N-1 reserve sizing and invisible embedded-generation
protection were the real failure, not the lightning."""),
])

# ---------------------------------------------------------------------------
NOTEBOOKS["03_pakistan_2023_uf_cascade.ipynb"] = nb([
    ("md", f"""# 03 · Pakistan, January 2023: the under-frequency cascade
{BOOK} See **Chapter 8, Section 8.2.3**.

Equations (8.1)-(8.2) of the book describe a self-reinforcing loop: each generator that trips on its own
under-frequency protection removes both power ($\\Delta P$ grows) and inertia ($H\\cdot S$ shrinks), so the
next threshold is reached faster.

This notebook builds an *illustrative* low-demand winter-morning system with thin reserve and generator
trip settings scattered between 49.2 and 48.0 Hz, then asks: what actually stops the cascade?

{DISCLAIMER} No public technical inquiry with unit-level data was available for this event (see ref. [27]),
so the fleet below is synthetic."""),
    ("code", SETUP),
    ("code", """from gridfail.frequency import FreqSystem, GenLoss, UFTrip, ShedStage, simulate, print_log

FLEET = [UFTrip(49.2, 350, 2500, 0.5, 'IPP A'), UFTrip(49.0, 500, 3500, 0.5, 'IPP B'),
         UFTrip(48.8, 600, 4000, 0.3, 'Thermal C'), UFTrip(48.6, 700, 5000, 0.3, 'Thermal D'),
         UFTrip(48.3, 900, 6000, 0.3, 'Plant E'), UFTrip(48.0, 1200, 8000, 0.2, 'Plant F')]
UFLS = [ShedStage(49.4, 300, 0.2, 'UFLS stage 1'), ShedStage(49.3, 400, 0.2, 'UFLS stage 2'),
        ShedStage(49.2, 500, 0.2, 'UFLS stage 3'), ShedStage(49.1, 600, 0.2, 'UFLS stage 4')]

def pakistan(reserve=200, ufls=False):
    s = FreqSystem(demand_mw=10500, ek_mws=50000, reserve_mw=reserve, reserve_tc=6,
                   load_damping=0.015,
                   losses=[GenLoss(0.0, 500, 3000, 'initiating loss (south)')],
                   uf_trips=FLEET, shed_stages=UFLS if ufls else [])
    return simulate(s, t_end=40, dt=0.005)

cases = {'A. As built: thin reserve (200 MW), no effective UFLS': pakistan(),
         'B. Triple the reserve (600 MW), still no UFLS': pakistan(reserve=600),
         'C. Thin reserve, but UFLS set ABOVE generator trips': pakistan(ufls=True)}

for lab, r in cases.items():
    print('==', lab, '| collapsed:', r['collapsed'])
    print_log(r); print()"""),
    ("code", """fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4), gridspec_kw=dict(width_ratios=[1.4, 1]))
for (lab, r), c in zip(cases.items(), ps.SERIES):
    ax1.plot(r['t'], r['f'], color=c, label=lab.split(':')[0] + (' (blackout)' if r['collapsed'] else ' (survives)'))
    if r['collapsed']:
        k = np.where(np.isnan(r['f']))[0][0] - 1
        ax1.plot(r['t'][k], r['f'][k], 'x', color=ps.CRITICAL, ms=9, mew=2)
ps.threshold(ax1, 47.0, 'collapse')
ax1.set_xlim(0, 25); ax1.set_ylim(46.8, 50.1)
ax1.set_xlabel('Time (s)'); ax1.set_ylabel('Frequency (Hz)')
ax1.set_title('Frequency'); ax1.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), fontsize=8.5)

r = cases['A. As built: thin reserve (200 MW), no effective UFLS']
k = ~np.isnan(r['f'])
ax2.plot(r['t'][k], 100 * r['ek'][k] / r['ek'][0], color=ps.SERIES[0], label='Inertia remaining (% of pre-event)')
ax2.plot(r['t'][k], 100 * r['lost'][k] / 10500, color=ps.SERIES[1], label='Generation lost (% of demand)')
ax2.set_xlim(0, 8); ax2.set_ylim(0, 105); ax2.set_xlabel('Time (s)'); ax2.set_ylabel('%')
ax2.set_title('Case A: deficit up, inertia down'); ax2.legend(loc='center left', fontsize=8.5)
fig.tight_layout()
fig.savefig(os.path.join(FIG, '03_pakistan_uf_cascade.png'))
plt.show()"""),
    ("md", """**Reading the result.** Tripling the reserve (case B) only delays the collapse by a couple of seconds,
because reserve is *slow* compared with protection. What saves the system is **coordination** (case C):
load-shedding stages set above the generators' own trip thresholds remove demand before the first
generator gives up. That is exactly lesson 2 of Chapter 8: *under-frequency relay settings must be
coordinated to avoid cascade amplification.*"""),
])

# ---------------------------------------------------------------------------
NOTEBOOKS["04_cascade_ieee39.ipynb"] = nb([
    ("md", f"""# 04 · Thermal cascade on the IEEE 39-bus system
{BOOK} See **Chapter 2, Section 2.5 (Figure 2.3)**, **Chapter 5** (Northeast 2003) and
**Chapter 18, Section 18.2.1** (operation close to limits).

The IEEE 39-bus "New England" test system is a standard 10-machine, 345 kV benchmark. We run the
overload -> trip -> redistribute loop from Figure 2.3 with a DC power flow:

1. trip one branch, 2. re-solve flows, 3. trip the most overloaded branch (protection doing its job on its
own element), 4. rebalance any islands (shed load if an island lacks generation), 5. repeat.

Relays trip at 120 % of the normal rating (a stand-in for an emergency rating).

{DISCLAIMER} A DC flow captures the thermal cascade but ignores voltage collapse; see notebook 05 for that."""),
    ("code", SETUP),
    ("code", """from gridfail.cascade import load_case39, cascade, n1_screen

TRIP = 1.2
sys39 = load_case39(load_scale=1.1)
r = cascade(sys39, ['L21-22'], trip_margin=TRIP)
total = sys39['load'].sum()
print(f"Initiating outage: line 21-22, system load {total:.0f} MW (110 % of base)\\n")
print(f"{'step':>4s}  {'tripped':10s} {'loading at trip':>16s} {'load served':>12s}")
for s in r['steps']:
    tl = ', '.join(f'{x*100:.0f}%' for x in s.get('trip_loading', [])) or '(initiating)'
    print(f"{s['step']:4d}  {', '.join(s['tripped']):10s} {tl:>16s} {s['served']:10.0f} MW")
print(f"\\nLoad lost: {r['load_lost_mw']:.0f} MW ({r['load_lost_pct']:.1f} %), branches tripped by protection: {r['n_tripped']}")"""),
    ("md", """## Operation close to limits: the cliff edge

Now screen **every** possible single initiating outage (all 46 lines and transformers), at increasing
system stress. Chapter 18 argues that margin, not the initiating event, decides whether a fault stays local."""),
    ("code", """import warnings; warnings.filterwarnings('ignore')
scales = np.round(np.arange(0.85, 1.31, 0.025), 3)
mean_lost, n_casc, worst = [], [], []
for ls in scales:
    res = n1_screen(load_case39(load_scale=ls), trip_margin=TRIP)
    pct = np.array([x[3] for x in res])
    mean_lost.append(pct.mean()); n_casc.append((pct > 1).sum()); worst.append(pct.max())

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
ax1.bar(scales * 100, n_casc, width=2.0, color=ps.SERIES[0])
ax1.set_xlabel('System load (% of base case)'); ax1.set_ylabel('Initiating outages (of 46)')
ax1.set_title('Single outages that cascade (>1 % load lost)')
ax2.plot(scales * 100, mean_lost, color=ps.SERIES[0], marker='o', ms=4, label='average over all 46 outages')
ax2.plot(scales * 100, worst, color=ps.SERIES[1], marker='s', ms=4, label='worst single outage')
ax2.set_xlabel('System load (% of base case)'); ax2.set_ylabel('Load lost (%)')
ax2.set_title('Expected vs worst-case load lost'); ax2.legend(loc='upper left')
fig.tight_layout()
fig.savefig(os.path.join(FIG, '04_cascade_cliff.png'))
plt.show()

for ls, n, m in zip(scales, n_casc, mean_lost):
    print(f"load {ls*100:5.1f} %   cascading outages {n:2d}/46   mean load lost {m:5.1f} %")"""),
    ("md", """**Reading the result.** Below about base load almost no single outage spreads. A few percent more load
and the number of dangerous initiating events jumps sharply: the same tree contact that is harmless at
90 % loading takes out a large share of the system at 115 %. Beyond roughly 113 % the intact network
already has a branch above the relay threshold, so the cascade no longer even needs a trigger. This is India 2012 (chronic overdrawl) and
Ohio 2003 (lines near thermal limits on a summer afternoon) in one chart.

**Try it:** set `trip_margin=1.0` (relays at normal rating) or `rating_scale=1.2` in `load_case39`
(reconductoring) and rerun the screen."""),
])

# ---------------------------------------------------------------------------
NOTEBOOKS["05_voltage_collapse_italy.ipynb"] = nb([
    ("md", f"""# 05 · Voltage collapse: P-V nose curves and the Italy 2003 mechanism
{BOOK} See **Chapter 2, Section 2.4 (Figure 2.2)** and **Chapter 7**.

A two-bus model: a strong external source (the UCTE grid) feeds an importing area over tie-lines of total
reactance $X$. Eliminating the angle from Eqs. (2.4)-(2.5) gives

$$V_r^4 + (2QX - V_s^2)V_r^2 + X^2(P^2+Q^2) = 0$$

whose two roots meet at the **nose point**, the maximum power the corridor can deliver.

The Italian story in model form: heavy imports over parallel tie-lines, one line trips (Lukmanier), the
equivalent reactance rises, the nose moves left, and an operating point that was safe is suddenly
beyond the nose. Over-excitation limits on Italian generators then removed reactive support (Eq. 7.1).

{DISCLAIMER} All quantities are per unit on an arbitrary base."""),
    ("code", SETUP),
    ("code", """from gridfail.voltage import nose_curve, pmax, vr_upper

X_line = 0.6          # pu, one tie-line
TAN = 0.2             # load power factor ~0.98 lagging
P_import = 1.05       # pu, pre-fault import

configs = [('Two lines in service (X = 0.30)', X_line / 2, 0.0),
           ('One line lost (X = 0.60)', X_line, 0.0),
           ('One line lost + 0.6 pu local reactive support', X_line, 0.6)]

fig, ax = plt.subplots()
for (lab, X, qc), c in zip(configs, ps.SERIES):
    P, vu, vl = nose_curve(X, TAN, q_comp=qc)
    ax.plot(P, vu, color=c, label=f'{lab}: Pmax = {P.max():.2f} pu')
    ax.plot(P, vl, color=c, ls=':', lw=1.4)
    ax.plot(P[-1], vu[-1], 'o', color=c, ms=7)
ax.axvline(P_import, color=ps.TEXT2, lw=1.2)
ax.annotate('pre-fault import', xy=(P_import, 0.15), xytext=(6, 0), textcoords='offset points', color=ps.TEXT2, fontsize=9)
ax.set_xlabel('Active power delivered P (pu)'); ax.set_ylabel('Receiving-end voltage Vr (pu)')
ax.set_title('Losing one tie-line moves the nose to the left of the operating point')
ax.set_ylim(0, 1.25); ax.set_xlim(0, None)
ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.16), ncol=1, fontsize=8.5)
fig.savefig(os.path.join(FIG, '05_pv_nose_italy.png'))
plt.show()

for lab, X, qc in configs:
    pm = pmax(X, TAN, q_comp=qc)
    v = float(vr_upper(P_import, P_import * TAN - qc, X))
    print(f"{lab:42s} Pmax {pm:4.2f} pu   margin {100*(pm-P_import)/P_import:6.1f} %   Vr at import: "
          + ('beyond nose -> collapse' if np.isnan(v) else f'{v:.3f} pu'))"""),
    ("md", """## Why generator reactive limits make it worse (Eq. 7.1)

$Q_{max,field} = \\dfrac{V_t E_f}{X_s} - \\dfrac{V_t^2}{X_s}$. As terminal voltage falls, the reactive power a
field-limited generator can supply falls too, exactly when the network needs more of it."""),
    ("code", """Vt = np.linspace(0.75, 1.05, 200)
Xs = 1.8
fig, ax = plt.subplots(figsize=(7.5, 4))
for Ef, c in zip([2.2, 2.0, 1.8], ps.SERIES):
    ax.plot(Vt, Vt * Ef / Xs - Vt**2 / Xs, color=c, label=f'field limit Ef = {Ef} pu')
ax.set_xlabel('Generator terminal voltage Vt (pu)'); ax.set_ylabel('Max reactive output (pu)')
ax.set_title('Field-limited reactive capability vs terminal voltage'); ax.legend(loc='upper left')
fig.savefig(os.path.join(FIG, '05_field_limit.png'))
plt.show()"""),
    ("md", """**Reading the result.** With both lines in, the import sits comfortably left of the nose. Lose one
line and the same import is no longer deliverable at any voltage, so voltage collapses rather than
merely sagging. Local reactive support near the load (FACTS/STATCOM, Chapter 20) pushes the nose back
to the right, which is why the book's lessons call for reactive compensation near import-dependent load
centres."""),
])


SCRIPT_SETUP = """import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import numpy as np
import matplotlib.pyplot as plt
from gridfail import plotstyle as ps
ps.apply()
FIG = os.path.join(ROOT, 'figures')
os.makedirs(FIG, exist_ok=True)"""


def write_scripts():
    """Write each notebook as a plain .py file in scripts/ (run with the PyCharm Run button)."""
    out_dir = os.path.join(ROOT, "scripts")
    os.makedirs(out_dir, exist_ok=True)
    for name, n in NOTEBOOKS.items():
        parts = []
        for c in n.cells:
            if c.cell_type == "markdown":
                parts.append("\n".join("# " + ln if ln else "#" for ln in c.source.splitlines()))
            elif c.source.strip() == SETUP:
                parts.append(SCRIPT_SETUP)
            else:
                parts.append(c.source)
        path = os.path.join(out_dir, name.replace(".ipynb", ".py"))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n\n\n".join(parts) + "\n")
        print("wrote", path)


def build(execute=True):
    ep = ExecutePreprocessor(timeout=600, kernel_name="python3")
    for name, n in NOTEBOOKS.items():
        path = os.path.join(NB_DIR, name)
        if execute:
            ep.preprocess(n, {"metadata": {"path": NB_DIR}})
        nbf.write(n, path)
        print("wrote", path)


if __name__ == "__main__":
    write_scripts()
    build()
