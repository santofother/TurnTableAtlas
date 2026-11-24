# Headless: rebuild the city in a fresh scene, print stats, optionally render one camera small.
import sys, importlib.util, json, os
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("fantasy_capital", os.path.join(root, "generator", "fantasy_capital.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
stats = m.build_all()
print("[Build] stats", json.dumps(stats))
hv = m.ANCHORS.get('venues', {}).get('hippodrome', {})
print("[Build] hippodrome anchors:", {k: (len(v) if isinstance(v, list) else v) for k, v in hv.items() if k not in ('seat_tiers',)},
      "tiers", [t['capacity'] for t in hv.get('seat_tiers', [])])
for a in argv:
    if a.startswith('render='):
        cam, out = a[7:].split(':', 1)
        m.render(out, cam, (960, 480), 16)
