"""Every cities/<id>/city.json must satisfy the v1 contract in docs/city_schema.md."""
import glob
import json
import math
import os
import unittest
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIRED = ['id', 'name', 'version', 'model_scale', 'extent', 'world_map', 'sun', 'files', 'street_graph',
            'spawn_zones', 'ship_lanes', 'moorings', 'venues', 'routes', 'night_lights', 'landmarks', 'events']
EVENTS = {'gladiator_games', 'chariot_race', 'theatre_play', 'fleet_arrival', 'festival_night'}
ESTATE_EVENTS = {'villa_return', 'villa_supper', 'villa_aegis', 'villa_cold_spring'}   # the villa's Chapter 1 scenes


def is_pt(p, n=3):
    return isinstance(p, list) and len(p) == n and all(isinstance(v, (int, float)) and math.isfinite(v) for v in p)


class ManifestTests(unittest.TestCase):
    def manifests(self):
        paths = sorted(glob.glob(os.path.join(ROOT, "cities", "*", "city.json")))
        self.assertTrue(paths, "no city packages built (run tools/build_city.sh fantasy_capital)")
        for p in paths:
            with open(p) as f:
                yield p, json.load(f)

    def test_required_keys_and_ids(self):
        for p, m in self.manifests():
            for k in REQUIRED:
                self.assertIn(k, m, "%s: missing %s" % (p, k))
            self.assertEqual(m['version'], 1)
            self.assertEqual(os.path.basename(os.path.dirname(p)), m['id'])
            self.assertTrue(set(m['events']) <= (ESTATE_EVENTS if m.get('kind') == 'estate' else EVENTS), m['events'])
            wm = m['world_map']
            # a pin on the painted Caelora map, or (for cities off Caelora) just a Known World settlement
            self.assertTrue('pin_uv' in wm or wm.get('settlement', '').startswith('settlement:'), p)
            if 'pin_uv' in wm:
                u, v = wm['pin_uv']
                self.assertTrue(0 <= u <= 1 and 0 <= v <= 1)
            s = m['sun']
            self.assertTrue(-90 <= s['latitude_deg'] <= 90 and 1 <= s['default_day_of_year'] <= 365)

    def test_street_graph_is_valid_and_connected(self):
        for p, m in self.manifests():
            g = m['street_graph']
            N, E = g['nodes'], g['edges']
            self.assertGreater(len(N), 200, p)
            self.assertTrue(all(is_pt(n) for n in N))
            adj = [[] for _ in N]
            for a, b, w in E:
                self.assertTrue(0 <= a < len(N) and 0 <= b < len(N) and a != b and w > 0)
                d = math.dist(N[a][:2], N[b][:2])
                self.assertLess(d, 2.5, "edge too long in %s" % p)
                adj[a].append(b)
                adj[b].append(a)
            seen, q = {0}, deque([0])
            while q:
                u = q.popleft()
                for v in adj[u]:
                    if v not in seen:
                        seen.add(v)
                        q.append(v)
            self.assertEqual(len(seen), len(N), "street graph not connected in %s" % p)

    def test_venues(self):
        for p, m in self.manifests():
            types = {v['type'] for v in m['venues']}
            self.assertTrue(types or m.get('kind') in ('estate', 'metropolis'), p)   # estates and Karn Ashur hold no shows
            for v in m['venues']:
                self.assertTrue(v['seat_tiers'], v['id'])
                for t in v['seat_tiers']:
                    self.assertEqual(len(t['ring']), t['capacity'])
                    self.assertTrue(all(is_pt(q) for q in t['ring']))
                self.assertTrue(all(is_pt(q) for q in v['entrances']))
                if v['type'] == 'circus':
                    self.assertGreater(len(v['track_centerline']), 20)
                    self.assertEqual(len(v['lane_radii']), v['lanes'])
                    self.assertGreaterEqual(len(v['start_gates']), v['lanes'])
                if v['type'] == 'arena':
                    self.assertGreaterEqual(len(v['floor_poly']), 8)
                if v['type'] == 'theatre':
                    self.assertGreaterEqual(len(v['stage']), 3)

    def test_lanes_zones_lights_landmarks_routes(self):
        for p, m in self.manifests():
            x0, y0, x1, y1 = m['extent']
            for ln in m['ship_lanes']:
                self.assertGreaterEqual(len(ln['points']), 2)
                for q in ln['points']:
                    self.assertTrue(x0 <= q[0] <= x1 and y0 <= q[1] <= y1, (ln['id'], q))
                if ln.get('then'):
                    self.assertIn(ln['then'], {l['id'] for l in m['ship_lanes']})
            for z in m['spawn_zones']:
                self.assertTrue(z['points'], "%s: empty zone %s" % (p, z['id']))
            kinds = {l['kind'] for l in m['night_lights']}
            self.assertTrue(kinds <= {'window', 'lamp', 'torch', 'lighthouse'})
            if m.get('kind', 'city') == 'city':
                self.assertIn('lighthouse', kinds)
            for l in m['night_lights']:
                if l['kind'] == 'window':
                    self.assertTrue(0 < l['order'] < 1)
            ids = [lm['id'] for lm in m['landmarks']]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertIn('overview', ids)
            for lm in m['landmarks']:
                c = lm['camera']
                self.assertTrue(is_pt(c['target']) and c['dist'] > 0 and -90 < c['pitch'] < 90)
            for rid, pts in m['routes'].items():
                self.assertGreater(len(pts), 5, rid)
                for a, b in zip(pts[:-1], pts[1:]):
                    self.assertLess(math.dist(a[:2], b[:2]), 2.5, rid)

    def test_estate_extras(self):
        """Estates (kind 'estate') carry named anchors, cutaway object prefixes and a ground grid for the map."""
        for p, m in self.manifests():
            if m.get('kind') != 'estate':
                continue
            self.assertTrue(m['events'], p)
            for ev in m['events']:                    # every scene has its timeline in the Atlas
                self.assertTrue(os.path.exists(os.path.join(ROOT, 'atlas', 'events', ev + '.json')), ev)
            for k, q in m['anchors'].items():
                self.assertTrue(is_pt(q), k)
            for k in ('gate_stop', 'private_dining', 'aegis_painting', 'cold_pool', 'heated_pool'):
                self.assertIn(k, m['anchors'])
            self.assertTrue(m['cutaway']['roofs'] and m['cutaway']['upper'])
            g = m['terrain_grid']
            self.assertEqual(len(g['z']), g['n'] * g['n'])
            self.assertTrue(min(g['z']) < 0 < max(g['z']), "the lake lies below 0, the land above")
            for rid in ('peristyle_loop', 'lagoon_riding_loop', 'garden_to_bath'):
                self.assertIn(rid, m['routes'])

    def test_metropolis_extras(self):
        """A metropolis (Karn Ashur, kind 'metropolis'): its instance table, its true-metre ground for the Known World,
        the basin layout the map patch draws, and the views and routes the brief asks for."""
        import struct
        for p, m in self.manifests():
            if m.get('kind') != 'metropolis':
                continue
            d = os.path.dirname(p)
            self.assertEqual(m['world_map']['settlement'], 'settlement:' + m['id'])
            ins = m['instances']
            size = os.path.getsize(os.path.join(d, ins['file']))
            self.assertEqual(size, ins['count'] * ins['stride'] * 4, "instances.bin length")
            covered = sorted((g[0], g[1]) for g in ins['groups'].values())
            self.assertEqual(sum(c for _, c in covered), ins['count'])
            self.assertEqual(covered[0][0], 0)
            for (a0, c0), (a1, _) in zip(covered, covered[1:]):
                self.assertEqual(a0 + c0, a1, "groups are contiguous runs of one kind")
            self.assertGreater(ins['groups']['house'][1], 40000, "an ocean of roofs")
            for kind in ('house', 'tower', 'terrace', 'warehouse', 'awning', 'camel', 'palm'):
                self.assertIn(kind, ins['protos'])
                self.assertIn(kind, ins['groups'])
            with open(os.path.join(d, ins['file']), 'rb') as f:              # the first and last records' kinds
                first = struct.unpack('<11f', f.read(44))
                f.seek(size - 44)
                last = struct.unpack('<11f', f.read(44))
            self.assertLessEqual(first[10], last[10])
            self.assertTrue(-50 <= first[0] <= 50 and -50 <= first[1] <= 50)
            th = m['terrain_height']
            self.assertTrue(os.path.exists(os.path.join(d, th['file'])))
            self.assertTrue(900 < th['min_m'] < 1100 and 3650 < th['max_m'] < 3800, "basin floor and the First Flame's summit")
            site = m['site']
            self.assertEqual(len(site['peaks']), 2)
            west, east = site['peaks']
            self.assertGreater(west['top_m'], east['top_m'], "the higher western peak carries the First Flame")
            self.assertIn('east_bank_quarter', site['districts'])
            self.assertIn('central_inundation_basins', site['fields'])
            self.assertLess(math.dist(west['at'], east['at']), 9.5)
            road = site['roads']['north_pass']
            self.assertEqual(road[0][1], site['plinth_half_km'])
            self.assertTrue(west['at'][0] < road[2][0] < east['at'][0])
            stream = site['rivers']['northern_pass_stream']
            self.assertTrue(all(a[2] > b[2] for a, b in zip(stream, stream[1:])))
            self.assertEqual(stream[-1][1], site['plinth_half_km'])
            self.assertLess(math.dist(stream[-1][:2], road[0]), 0.5)
            for rid in ('western_snowmelt', 'eastern_snowmelt', 'southern_outlet'):
                beds = [q[2] for q in site['rivers'][rid]]
                self.assertTrue(all(b <= a for a, b in zip(beds, beds[1:])), rid + " runs downhill")
            ids = {lm['id'] for lm in m['landmarks']}
            self.assertTrue({'caravan_arrival', 'terraces', 'downstream', 'al_mirah', 'first_flame', 'library'} <= ids)
            pil = m['routes']['pilgrimage']
            flame = m['anchors']['first_flame']
            self.assertLess(math.dist(pil[-1][:2], flame[:2]), 1.0, "the pilgrims' route ends at the First Flame")
            self.assertGreater(pil[-1][2] - pil[0][2], 10, "it climbs")
            self.assertTrue(any(l['kind'] == 'lighthouse' for l in m['night_lights']), "the flame burns at night")
            pop = m['stats']['population_estimate']
            self.assertTrue(400000 < pop < 650000, pop)

    def test_calderra_boat_voyages(self):
        for _, m in self.manifests():
            if m['id'] != 'fantasy_capital':
                continue
            ships = m['moorings'] + m['anchored_ships'] + m['boats']
            x0, y0, x1, y1 = m['extent']
            for ship in ships:
                voyage = ship['voyage']
                points = voyage['points']
                self.assertGreater(len(points), 3, ship['object'])
                self.assertTrue(all(is_pt(q, 2) and x0 <= q[0] <= x1 and y0 <= q[1] <= y1 for q in points))
                self.assertGreater(voyage['speed'], 0)
                self.assertGreaterEqual(voyage['phase_s'], 0)
                if ship['kind'].startswith('moored'):
                    self.assertGreaterEqual(voyage['dwell_s'], 45)
                if voyage['dwell_s']:
                    self.assertEqual(points[0], ship['pos'][:2])
                    self.assertEqual(points[-1], points[0])
                else:
                    self.assertNotEqual(points[0], points[-1])

    def test_package_files_exist(self):
        for p, m in self.manifests():
            d = os.path.dirname(p)
            for key in ('model', 'proxies', 'terrain_albedo', 'thumb'):
                if os.environ.get('SKIP_PACKAGE_FILES'):
                    continue
                self.assertTrue(os.path.exists(os.path.join(d, m['files'][key])), "%s: missing %s" % (p, m['files'][key]))


if __name__ == "__main__":
    unittest.main()
