"""Tiny Geometry Nodes builder (Blender 5.x) so the crowd/venue node trees stay readable as Python."""
import bpy


def avail(s):
    return getattr(s, 'enabled', True) and not getattr(s, 'is_unavailable', False)


class GN:
    def __init__(self, name):
        old = bpy.data.node_groups.get(name)
        if old is not None:
            bpy.data.node_groups.remove(old)
        self.ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
        self.ng.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
        self.ng.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
        self.gi = self.ng.nodes.new('NodeGroupInput')
        self.go = self.ng.nodes.new('NodeGroupOutput')
        self.ids = {}
        self._x = 0

    # --- interface
    def input(self, name, stype, default=None, mn=None, mx=None):
        it = self.ng.interface.new_socket(name=name, in_out='INPUT', socket_type=stype)
        if default is not None:
            it.default_value = default
        if mn is not None:
            it.min_value = mn
        if mx is not None:
            it.max_value = mx
        self.ids[name] = it.identifier
        return self.gi.outputs[name]

    def output(self, geo):
        self.link(geo, self.go.inputs[0])

    # --- nodes and sockets
    def node(self, typ, **props):
        n = self.ng.nodes.new(typ)
        self._x += 40
        n.location = (self._x, 0)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    @staticmethod
    def sock(socks, key):
        for s in socks:
            if s.identifier == key:
                return s
        for s in socks:
            if s.name == key and avail(s):
                return s
        for s in socks:
            if s.name == key:
                return s
        raise KeyError(key)

    def i(self, n, key):
        return self.sock(n.inputs, key)

    def o(self, n, key=None):
        if key is None:
            for s in n.outputs:
                if avail(s):
                    return s
        return self.sock(n.outputs, key)

    def link(self, a, b):
        self.ng.links.new(a, b)

    def set(self, sock, val):
        if isinstance(val, bpy.types.NodeSocket):
            self.link(val, sock)
        elif val is not None:
            sock.default_value = val

    def wire(self, n, **inputs):
        for k, v in inputs.items():
            self.set(self.i(n, k.replace('__', ' ')), v)
        return n

    # --- common ops
    def math(self, op, a, b=None, c=None):
        n = self.node('ShaderNodeMath', operation=op)
        for s, v in zip(n.inputs, (a, b, c)):
            self.set(s, v)
        return n.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        n = self.node('ShaderNodeVectorMath', operation=op)
        self.set(n.inputs[0], a)
        if b is not None:
            self.set(n.inputs[1], b)
        if scale is not None:
            self.set(self.i(n, 'Scale'), scale)
        return self.o(n, 'Value' if op in ('LENGTH', 'DOT_PRODUCT', 'DISTANCE') else 'Vector')

    def rand(self, dtype, mn, mx, seed, ident=None):
        n = self.node('FunctionNodeRandomValue', data_type=dtype)
        self.set(self.i(n, 'Min'), mn)
        self.set(self.i(n, 'Max'), mx)
        self.set(self.i(n, 'Seed'), seed)
        if ident is not None:
            self.set(self.i(n, 'ID'), ident)
        return self.o(n, 'Value')

    def compare(self, op, a, b, dtype='FLOAT'):
        n = self.node('FunctionNodeCompare', data_type=dtype, operation=op)
        self.set(self.i(n, 'A'), a)
        self.set(self.i(n, 'B'), b)
        return self.o(n, 'Result')

    def combine(self, x, y, z):
        n = self.node('ShaderNodeCombineXYZ')
        for s, v in zip(n.inputs, (x, y, z)):
            self.set(s, v)
        return n.outputs[0]

    def separate(self, v):
        n = self.node('ShaderNodeSeparateXYZ')
        self.set(n.inputs[0], v)
        return n.outputs

    def named(self, name, dtype='FLOAT'):
        n = self.node('GeometryNodeInputNamedAttribute', data_type=dtype)
        self.i(n, 'Name').default_value = name
        return self.o(n, 'Attribute')

    def store(self, geo, name, value, dtype='FLOAT', domain='POINT'):
        n = self.node('GeometryNodeStoreNamedAttribute', data_type=dtype, domain=domain)
        self.set(self.i(n, 'Geometry'), geo)
        self.i(n, 'Name').default_value = name
        self.set(self.i(n, 'Value'), value)
        return n.outputs[0]

    def time(self):
        return self.o(self.node('GeometryNodeInputSceneTime'), 'Seconds')

    def align_x(self, vec):
        n = self.node('FunctionNodeAlignRotationToVector', axis='X', pivot_axis='Z')
        self.set(self.i(n, 'Vector'), vec)
        return n.outputs[0]

    def euler_rot(self, euler):
        n = self.node('FunctionNodeEulerToRotation')
        self.set(n.inputs[0], euler)
        return n.outputs[0]


def _ident(ng, name):
    return next(it.identifier for it in ng.interface.items_tree if getattr(it, 'in_out', '') == 'INPUT' and it.name == name)


def _input(mod, ident):
    """Blender 5.x: modifier inputs live at mod.properties.inputs.<identifier>.value (older: mod[identifier])."""
    props = getattr(mod, 'properties', None)
    if props is not None and hasattr(props, 'inputs'):
        return getattr(props.inputs, ident), 'modifiers["%s"].properties.inputs.%s.value' % (mod.name, ident)
    return None, 'modifiers["%s"]["%s"]' % (mod.name, ident)


def set_input(ob, name, value, mod_name="CIN"):
    mod = ob.modifiers[mod_name]
    ident = _ident(mod.node_group, name)
    sock, path = _input(mod, ident)
    if sock is not None:
        sock.value = value
    else:
        mod[ident] = value
    return path


def add_modifier(ob, ng, values):
    mod = ob.modifiers.new("CIN", 'NODES')
    mod.node_group = ng
    for name, val in values.items():
        set_input(ob, name, val)
    return mod


def key_input(ob, name, value, frame):
    path = set_input(ob, name, value)
    ob.keyframe_insert(path, frame=frame)
