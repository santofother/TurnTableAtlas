"""Build recurring routes for placed boats, in the city manifest's XY frame."""

import numpy as np


def smooth(points, closed):
    points = np.asarray(points, float)
    for _ in range(2):
        a = points if closed else points[:-1]
        b = np.roll(points, -1, axis=0) if closed else points[1:]
        pairs = np.stack((0.75 * a + 0.25 * b, 0.25 * a + 0.75 * b), axis=1).reshape(-1, 2)
        points = pairs if closed else np.vstack((points[0], pairs, points[-1]))
    return points


def build(m, terrain, ships, config):
    if not config:
        return

    circuits = config['circuits']
    docks = config['berth_exits']
    used = [0] * len(circuits)
    for index, ship in enumerate(ships):
        berth = docks.get(ship['object'])
        dwell = 0
        if berth:
            # Follow the berth approach back after a circuit of the harbour.
            approach = [ship['pos'][:2], *berth]
            circuit = config['berth_circuit']
            first = int(np.argmin(np.linalg.norm(np.asarray(circuit) - approach[-1], axis=1)))
            circuit = circuit[first:] + circuit[:first]
            points = smooth(approach + circuit + approach[::-1], False)
            speed = 0.7
            dwell = 45 + index % 8 * 5
            # Some moored ships are already out on the water at the start.
            phase = dwell + 7 + index % 5 * 3 if index % 4 == 0 else dwell * (0.08 + index % 7 * 0.12)
        else:
            eligible = [i for i, route in enumerate(circuits) if ship['kind'] in route['kinds']]
            i = min(eligible, key=lambda i: (
                np.min(np.linalg.norm(np.asarray(circuits[i]['points']) - ship['pos'][:2], axis=1))
                + 0.85 * used[i]
            ))
            route = circuits[i]
            points = smooth(route['points'], True)
            speed = route['speed']
            # Alternate halves of the route before filling in the gaps.
            phase = (0.11 + used[i] * 0.61803398875) % 1
            used[i] += 1

        points = np.round(points, 3)
        path = np.vstack((points, points[0])) if not dwell else points
        samples = m.resample(path, 0.12)
        x, y = samples.T
        margin = 0.34 if ship['kind'] == 'boat' else 0.58
        if (terrain.h(x, y).max() > -0.15
                or any(m.dist_to_polyline(x, y, pier).min() < margin for pier in m.PIERS)
                or any(m.dist_to_polyline(x, y, mole).min() < 1.65 for mole in (m.W_MOLE, m.E_MOLE) if mole)):
            raise ValueError(f"Boat route intersects the shore, a pier or a mole: {ship['object']}")
        if not dwell:
            phase *= m.arclen(path)[-1] / speed
        ship['voyage'] = {'points': points.tolist(), 'speed': speed, 'dwell_s': dwell, 'phase_s': round(phase, 3)}
