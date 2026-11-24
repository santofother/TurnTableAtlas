"""Tiny low-poly props shared by the Blender cinematic and the Atlas (exported to atlas/assets/props.glb):
people (about 0.11 m tall at 1:15), a seated spectator, a gladiator, a chariot with its team, a beast, a torch.

Pure Python (no bpy). Each prop is (verts, faces, colors) with one RGBA colour per face. Alpha marks tint slots:
alpha 0.5 = 'tint' (clothes: per-instance colour), 1.0 = fixed colour. Figures face +X, feet at z = 0.
"""
import math

SKIN = (0.80, 0.58, 0.44)
SKIN_D = (0.62, 0.42, 0.30)
HAIR = (0.20, 0.13, 0.08)
TINT = (0.85, 0.80, 0.70)
METAL = (0.70, 0.68, 0.62)
WOOD = (0.42, 0.29, 0.17)
GOLD = (0.85, 0.66, 0.28)


class P:
    def __init__(self):
        self.v, self.f, self.c = [], [], []

    def box(self, cx, cy, z0, w, d, h, col, tint=False, taper=1.0, rot=0.0):
        c, s = math.cos(rot), math.sin(rot)
        def pt(x, y, z):
            return (cx + x * c - y * s, cy + x * s + y * c, z)
        b = len(self.v)
        hw, hd = w / 2, d / 2
        tw, td = hw * taper, hd * taper
        self.v += [pt(-hw, -hd, z0), pt(hw, -hd, z0), pt(hw, hd, z0), pt(-hw, hd, z0),
                   pt(-tw, -td, z0 + h), pt(tw, -td, z0 + h), pt(tw, td, z0 + h), pt(-tw, td, z0 + h)]
        a = 0.5 if tint else 1.0
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self.f.append(tuple(b + i for i in f))
            self.c.append((*col, a))

    def ball(self, cx, cy, cz, r, col, tint=False, n=6):
        """Low-poly sphere (n sides, 3 rings)."""
        b = len(self.v)
        self.v.append((cx, cy, cz - r))
        for la in (-0.5, 0.5):
            rr = r * math.cos(la)
            self.v += [(cx + rr * math.cos(2 * math.pi * k / n), cy + rr * math.sin(2 * math.pi * k / n), cz + r * math.sin(la))
                       for k in range(n)]
        self.v.append((cx, cy, cz + r))
        a = 0.5 if tint else 1.0
        top = b + 1 + 2 * n
        for k in range(n):
            k2 = (k + 1) % n
            for f in ((b, b + 1 + k2, b + 1 + k), (b + 1 + k, b + 1 + k2, b + 1 + n + k2, b + 1 + n + k),
                      (b + 1 + n + k, b + 1 + n + k2, top)):
                self.f.append(f)
                self.c.append((*col, a))

    def out(self):
        return self.v, self.f, self.c


def citizen():
    p = P()
    for s in (-1, 1):
        p.box(0.0, s * 0.0065, 0.0, 0.011, 0.010, 0.045, SKIN_D)
    p.box(0.0, 0.0, 0.040, 0.026, 0.032, 0.048, TINT, tint=True, taper=0.85)
    for s in (-1, 1):
        p.box(0.002, s * 0.019, 0.050, 0.009, 0.008, 0.034, TINT, tint=True)
    p.ball(0.0, 0.0, 0.097, 0.0105, SKIN)
    p.box(-0.002, 0.0, 0.100, 0.018, 0.020, 0.008, HAIR)
    return p.out()


def robed():
    p = P()
    p.box(0.0, 0.0, 0.0, 0.034, 0.034, 0.088, TINT, tint=True, taper=0.62)
    for s in (-1, 1):
        p.box(0.003, s * 0.016, 0.045, 0.009, 0.008, 0.036, TINT, tint=True)
    p.ball(0.0, 0.0, 0.098, 0.0105, SKIN)
    p.box(-0.003, 0.0, 0.098, 0.020, 0.022, 0.012, HAIR, taper=0.8)
    return p.out()


def seated():
    p = P()
    p.box(0.006, 0.0, 0.0, 0.030, 0.026, 0.030, TINT, tint=True)
    p.box(0.0, 0.0, 0.028, 0.024, 0.030, 0.040, TINT, tint=True, taper=0.85)
    p.ball(0.0, 0.0, 0.080, 0.0105, SKIN)
    p.box(-0.002, 0.0, 0.084, 0.018, 0.020, 0.008, HAIR)
    return p.out()


def gladiator():
    p = P()
    for s in (-1, 1):
        p.box(0.0, s * 0.0065, 0.0, 0.012, 0.011, 0.046, SKIN_D)
    p.box(0.0, 0.0, 0.040, 0.026, 0.032, 0.020, TINT, tint=True)
    p.box(0.0, 0.0, 0.060, 0.022, 0.030, 0.028, SKIN, taper=0.9)
    p.ball(0.0, 0.0, 0.099, 0.012, METAL)
    p.box(0.004, 0.0, 0.110, 0.006, 0.004, 0.012, (0.70, 0.15, 0.10))
    p.box(0.010, -0.024, 0.040, 0.006, 0.026, 0.042, TINT, tint=True)              # shield
    p.box(0.016, 0.022, 0.065, 0.030, 0.004, 0.004, METAL)                        # sword
    return p.out()


def beast():
    p = P()
    col = (0.70, 0.52, 0.28)
    p.box(0.0, 0.0, 0.035, 0.085, 0.034, 0.034, col, taper=0.95)
    for x in (-0.03, 0.03):
        for y in (-0.011, 0.011):
            p.box(x, y, 0.0, 0.010, 0.010, 0.038, col)
    p.ball(0.052, 0.0, 0.068, 0.019, (0.55, 0.36, 0.18))
    p.box(-0.05, 0.0, 0.058, 0.030, 0.006, 0.006, col, rot=0.5)
    return p.out()


def chariot():
    """Car + charioteer + four horses; faces +X. The car's colour slot is the team tint."""
    p = P()
    p.box(0.0, 0.0, 0.014, 0.10, 0.11, 0.065, TINT, tint=True, taper=0.9)
    for s in (-1, 1):
        p.box(0.0, s * 0.062, 0.0, 0.06, 0.012, 0.06, WOOD)
    p.box(0.0, 0.0, 0.079, 0.026, 0.03, 0.03, TINT, tint=True)
    p.ball(0.0, 0.0, 0.118, 0.0105, SKIN)
    p.box(0.10, 0.0, 0.04, 0.12, 0.012, 0.010, WOOD)
    horse = [(0.40, 0.25, 0.14), (0.15, 0.10, 0.08), (0.92, 0.90, 0.86), (0.55, 0.36, 0.20)]
    for i, oy in enumerate((-0.075, -0.025, 0.025, 0.075)):
        hx = 0.22
        hc = horse[i]
        p.box(hx, oy, 0.060, 0.17, 0.035, 0.060, hc)
        for lx in (-0.055, 0.055):
            p.box(hx + lx, oy, 0.0, 0.014, 0.014, 0.062, hc)
        p.box(hx + 0.10, oy, 0.090, 0.050, 0.030, 0.070, hc, taper=0.8)
    return p.out()


def torch_bearer():
    v, f, c = robed()
    p = P()
    p.v, p.f, p.c = list(v), list(f), list(c)
    p.box(0.012, 0.018, 0.06, 0.005, 0.005, 0.07, WOOD)
    p.ball(0.012, 0.018, 0.135, 0.008, (1.0, 0.75, 0.35))
    return p.out()


def horse():
    """A saddled horse at 1:15 (withers ~0.107 = 1.6 m), facing +X. The coat is the tint slot; mane, tail, hooves fixed."""
    p = P()
    mane = (0.12, 0.09, 0.07)
    p.box(0.0, 0.0, 0.062, 0.120, 0.036, 0.040, TINT, tint=True, taper=0.92)              # barrel
    p.box(0.052, 0.0, 0.070, 0.040, 0.034, 0.036, TINT, tint=True)                          # chest
    for x in (-0.046, 0.046):
        for y in (-0.011, 0.011):
            p.box(x, y, 0.0, 0.010, 0.010, 0.066, TINT, tint=True)
            p.box(x, y, 0.0, 0.012, 0.012, 0.006, mane)                                     # hooves
    p.box(0.078, 0.0, 0.092, 0.024, 0.018, 0.040, TINT, tint=True, rot=0.0, taper=0.8)      # neck
    p.box(0.094, 0.0, 0.128, 0.040, 0.016, 0.016, TINT, tint=True)                          # head
    p.box(0.070, 0.0, 0.110, 0.022, 0.006, 0.026, mane)                                     # mane
    p.box(-0.066, 0.0, 0.050, 0.008, 0.008, 0.050, mane)                                    # tail
    p.box(-0.004, 0.0, 0.100, 0.036, 0.040, 0.006, (0.36, 0.20, 0.10))                      # saddle
    return p.out()


def rider():
    """A rider astride, origin on the ground under the horse's back (sits at 0.106): clothes are the tint slot."""
    p = P()
    for s in (-1, 1):
        p.box(0.004, s * 0.022, 0.072, 0.012, 0.008, 0.036, TINT, tint=True)               # legs down the flanks
        p.box(0.008, s * 0.022, 0.066, 0.016, 0.010, 0.008, HAIR)                          # boots
    p.box(-0.002, 0.0, 0.104, 0.024, 0.040, 0.010, TINT, tint=True)
    p.box(-0.002, 0.0, 0.112, 0.024, 0.030, 0.044, TINT, tint=True, taper=0.85)
    for s in (-1, 1):
        p.box(0.010, s * 0.017, 0.126, 0.020, 0.008, 0.008, TINT, tint=True)                 # arms to the reins
    p.ball(0.0, 0.0, 0.168, 0.0105, SKIN)
    p.box(-0.002, 0.0, 0.171, 0.018, 0.020, 0.008, HAIR)
    return p.out()


PROPS = {'horse': horse, 'rider': rider, 'citizen': citizen, 'robed': robed, 'seated': seated, 'gladiator': gladiator, 'beast': beast,
         'chariot': chariot, 'torch_bearer': torch_bearer}

# clothing palette for tints (sRGB): earthy wool, linen, ochre, madder red, woad blue, a few whites
PALETTE = [(0.86, 0.82, 0.72), (0.74, 0.62, 0.44), (0.62, 0.30, 0.20), (0.36, 0.42, 0.55), (0.55, 0.50, 0.30),
           (0.80, 0.70, 0.48), (0.45, 0.32, 0.25), (0.92, 0.90, 0.86), (0.66, 0.46, 0.52), (0.40, 0.48, 0.36)]
TEAMS = [(0.78, 0.12, 0.10), (0.15, 0.30, 0.72), (0.18, 0.55, 0.20), (0.95, 0.95, 0.92)]


def to_blender(name, prop, coll=None, mats=()):
    """Build a bpy mesh/object for a prop (Col attribute in linear space, alpha = tint flag)."""
    import bpy
    import numpy as np
    v, f, c = prop() if callable(prop) else prop
    me = bpy.data.meshes.get(name)
    if me is None:
        me = bpy.data.meshes.new(name)
        me.from_pydata(v, [], f)
        me.update()
        lt = np.fromiter((len(x) for x in f), dtype=np.int64, count=len(f))
        cc = np.asarray(c, np.float64)
        rgb = np.where(cc[:, :3] <= 0.04045, cc[:, :3] / 12.92, ((cc[:, :3] + 0.055) / 1.055) ** 2.4)
        rgba = np.column_stack([rgb, cc[:, 3]]).astype(np.float32)
        at = me.color_attributes.new('Col', 'FLOAT_COLOR', 'CORNER')
        at.data.foreach_set('color', np.repeat(rgba, lt, axis=0).ravel())
        for m in mats:
            me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    if coll is not None:
        coll.objects.link(ob)
    return ob
