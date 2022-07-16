from ._core import _BaseTraceGenerator

class CounterTrack:
    def __init__(self, name, parent, uuid):
        self._parent = parent
        self._uuid = uuid
        self._name = name
    def count(self, ts, value):
        """ Add a count value on the track. """
        self._parent._track_count(self._uuid, ts, value)
        return self

class NormalTrack:
    def __init__(self, name, parent, uuid):
        self._parent = parent
        self._uuid = uuid
        self._name = name
    def open(self, ts, annotation, kwargs = None, flow = []):
        """ Open a track. """
        self._parent._track_open(self._uuid, ts, annotation, kwargs, flow)
        return self

    def close(self, ts, flow = []):
        """ Close a track.  The last 'open' call is closed """
        self._parent._track_close(self._uuid, ts, flow)
        return self

    def instant(self, ts, annotation, kwargs = None, flow = []):
        """ Record an instant event. """
        self._parent._track_instant(self._uuid, ts, annotation, kwargs, flow)
        return self

class GroupTrack:
    def __init__(self, name, parent, uuid):
        self._parent = parent
        self._uuid = uuid
        self._name = name

    def create_track(self) -> NormalTrack:
        """ Create a child track for this track."""
        return self._parent._create_track(self._uuid, self._name, 0)

class Group:
    def __init__(self, name, parent, uuid):
        self._parent = parent
        self._uuid = uuid

    def create_track(self, track_name : str) -> NormalTrack:
        """ Create a normal track for this track."""
        return self._parent._create_track(self._uuid, track_name, 0)

    def create_counter_track(self, track_name : str) -> CounterTrack:
        """ Create a counter track.  Counter tracks can be used for recording int values."""
        return self._parent._create_track(self._uuid, track_name, 1)

    def create_group(self, track_name : str) -> GroupTrack:
        """ Create a group track.  Group tracks can be used for grouping normal tracks."""
        return self._parent._create_track(self._uuid, track_name, 2)

    def open(self, ts : int, annotation : str, kwargs : dict = None, flow : list = []):
        """ Open track. """
        self._parent._track_open(self._uuid, ts, annotation, kwargs, flow)

    def close(self, ts : int, flow : list = []):
        """ Close a track.  The last 'open' call is closed """
        self._parent._track_close(self._uuid, ts, flow)

    def instant(self, ts : int, annotation : str, kwargs : dict = None, flow : list = []):
        """ Record an instant event. """
        self._parent._track_instant(self._uuid, ts, annotation, kwargs, flow)


class TraceGenerator(_BaseTraceGenerator):
    def __init__(self, filename : str):
        """ Create a trace """
        super().__init__(filename)
        self.__pid__ = 1

    def create_group(self, process_name : str, track_name : str = None):
        """ Create a group.  Each "group" comes with a default normal track (named track_name)."""
        pid = self.__pid__
        self.__pid__ += 1

        uuid = self._pid_packet(pid, process_name, track_name)
        return Group(process_name, self, uuid)

    def _create_track(self, parent_uuid, track_name, ttype):
        tid = self.__pid__
        self.__pid__ += 1

        uuid = self._tid_packet(tid, parent_uuid, track_name, ttype)

        if ttype == 0:
            return NormalTrack(track_name, self, uuid)
        elif ttype == 1:
            return CounterTrack(track_name, self, uuid)
        elif ttype == 2:
            return GroupTrack(track_name, self, uuid)
        else:
            assert False

    def create_counter_track(self, track_name : str):
        """ Create a global counter track """
        return self._create_track(0, track_name, 1)



