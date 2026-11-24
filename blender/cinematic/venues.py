"""Venue life: crowds streaming in, seats filling in random order, cheering, and emptying afterwards.

    vl = VenueLife(crowds, man, 'colosseum')
    vl.schedule(f_open, f_full, f_event_end, f_empty)    # keyframes stream + fill + excitement
"""
import cine
import crowds as crowds_mod


class VenueLife:
    def __init__(self, crowds, man, venue_id, stream_count=600):
        self.c, self.man, self.vid = crowds, man, venue_id
        self.v = next(v for v in man['venues'] if v['id'] == venue_id)
        crowds.add_seats(venue_id, fill=0.0)
        self.paths = crowds_mod.stream_paths(man, venue_id, name="CIN_StreamPaths_" + venue_id)
        self.stream_count = stream_count

    def schedule(self, f_open, f_full, f_end=None, f_empty=None, base_fill=0.0, full=0.97):
        s_open = (f_open - 1) / cine.FPS
        s_full = (f_full - 1) / cine.FPS
        self.c.add_stream(self.vid + "_in", self.paths, self.stream_count, s_open, max(1.0, s_full - s_open - 6.0))
        self.c.key_fill(self.vid, 1, base_fill, 0.0)
        self.c.key_fill(self.vid, f_open, base_fill, 0.0)
        self.c.key_fill(self.vid, f_full, full, 0.1)
        if f_end is not None:
            self.c.key_fill(self.vid, f_end, full, 0.1)
        if f_empty is not None:
            s_end = (f_end - 1) / cine.FPS
            self.c.add_stream(self.vid + "_out", self.paths, self.stream_count, s_end + 2.0,
                              max(1.0, (f_empty - f_end) / cine.FPS - 6.0), reverse=True)
            self.c.key_fill(self.vid, f_empty, base_fill, 0.0)

    def cheer(self, frame, amount, ramp=12):
        self.c.key_fill(self.vid, frame - ramp, self.current_fill(frame), 0.1)
        self.c.key_fill(self.vid, frame, self.current_fill(frame), amount)
        self.c.key_fill(self.vid, frame + ramp * 4, self.current_fill(frame), 0.1)

    def current_fill(self, frame):
        return 0.97
