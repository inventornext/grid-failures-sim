"""Run every case-study simulation in order. In PyCharm: right-click this file -> Run 'run_all'.

Each script prints its results and opens its charts. Close a chart window to move on.
Figures are also saved to the figures/ folder.
"""
import os, runpy, glob

HERE = os.path.dirname(os.path.abspath(__file__))
for path in sorted(glob.glob(os.path.join(HERE, "scripts", "0*.py"))):
    print("\n" + "=" * 70 + f"\n{os.path.basename(path)}\n" + "=" * 70)
    runpy.run_path(path, run_name="__main__")
