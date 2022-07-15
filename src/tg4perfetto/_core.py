from . import perfetto_trace_pb2 as pb2

class CounterTrack:
    def __init__(self, name, parent, tid):
        self._parent = parent
        self._tid = tid
        self._name = name
    def count(self, ts, value):
        """ Add a count value on the track. """
        self._parent._track_count(self._tid, ts, value)
        return self

class NormalTrack:
    def __init__(self, name, parent, tid):
        self._parent = parent
        self._tid = tid
        self._name = name
    def open(self, ts, annotation, kwargs = None, flow = []):
        """ Open a track. """
        self._parent._track_open(self._tid, ts, annotation, kwargs, flow)
        return self

    def close(self, ts, flow = []):
        """ Close a track.  The last 'open' call is closed """
        self._parent._track_close(self._tid, ts, flow)
        return self

    def instant(self, ts, annotation, kwargs = None, flow = []):
        """ Record an instant event. """
        self._parent._track_instant(self._tid, ts, annotation, kwargs, flow)
        return self

class GroupTrack:
    def __init__(self, name, parent, pid):
        self._parent = parent
        self._pid = pid
        self._name = name

    def create_track(self) -> NormalTrack:
        """ Create a child track for this track."""
        return self._parent._tid_packet(self._pid, self._name, 0)

class Group:
    def __init__(self, name, parent, pid):
        self._parent = parent
        self._pid = pid

    def create_track(self, track_name : str) -> NormalTrack:
        """ Create a normal track for this track."""
        return self._parent._tid_packet(self._pid, track_name, 0)

    def create_counter_track(self, track_name : str) -> CounterTrack:
        """ Create a counter track.  Counter tracks can be used for recording int values."""
        return self._parent._tid_packet(self._pid, track_name, 1)

    def create_group(self, track_name : str) -> GroupTrack:
        """ Create a group track.  Group tracks can be used for grouping normal tracks."""
        return self._parent._tid_packet(self._pid, track_name, 2)

    def open(self, ts : int, annotation : str, kwargs : dict = None, flow : list = []):
        """ Open track. """
        self._parent._track_open(self._pid, ts, annotation, kwargs, flow)

    def close(self, ts : int, flow : list = []):
        """ Close a track.  The last 'open' call is closed """
        self._parent._track_close(self._pid, ts, flow)

    def instant(self, ts : int, annotation : str, kwargs : dict = None, flow : list = []):
        """ Record an instant event. """
        self._parent._track_instant(self._pid, ts, annotation, kwargs, flow)


class TraceGenerator:
    def __init__(self, filename : str):
        """ Create a trace """
        self.__uuid__ = 1234567
        self.__pid__ = 1
        self.pid2uuid = {}
        self.interned_data = {}
        self.flush_threshold = 10000

        self.trace = pb2.Trace()
        self.file = open(filename, "wb")

        pkt = self.trace.packet.add()
        pkt.trusted_packet_sequence_id = 1
        clk = pkt.clock_snapshot.clocks.add()
        clk.clock_id = 1
        clk.timestamp = 0
        clk = pkt.clock_snapshot.clocks.add()
        clk.clock_id = 2 
        clk.timestamp = 0
        clk = pkt.clock_snapshot.clocks.add()
        clk.clock_id = 3
        clk.timestamp = 0
        clk = pkt.clock_snapshot.clocks.add()
        clk.clock_id = 4
        clk.timestamp = 0
        clk = pkt.clock_snapshot.clocks.add()
        clk.clock_id = 5
        clk.timestamp = 0
        clk = pkt.clock_snapshot.clocks.add()
        clk.clock_id = 6
        clk.timestamp = 0
        pkt.clock_snapshot.primary_trace_clock = pb2.BUILTIN_CLOCK_BOOTTIME
    
        pkt = self.trace.packet.add()
        pkt.trusted_packet_sequence_id = 1
        pkt.trace_config.buffers.add().size_kb = 1024
        pkt.trace_config.data_sources.add().config.name = "track_event"
    
        pkt = self.trace.packet.add()
        pkt.trusted_packet_sequence_id = 2
        pkt.trace_packet_defaults.track_event_defaults.track_uuid=1
        pkt.trace_packet_defaults.timestamp_clock_id = 1
        pkt.sequence_flags = 1


    def flush(self):
        """ Flush trace.  This creates a perfetto trace packet and writes to disk. """
        # print(self.trace)
        self.file.write(self.trace.SerializeToString())
        self.file.flush()
        self.trace = pb2.Trace()

    def __del__(self):
        self.flush()
        self.file.close()

    def create_group(self, process_name : str, track_name : str = None):
        """ Create a group.  Each "group" comes with a default normal track (named track_name)."""
        pkt = self.trace.packet.add()
        pkt.timestamp = 0
        pkt.track_descriptor.uuid = self.__uuid__
        pid = self.__pid__
        pkt.track_descriptor.process.pid = pid
        pkt.track_descriptor.process.process_name = process_name
        pkt.trusted_packet_sequence_id = 2
        pkt.sequence_flags = 2
        if track_name is None:
            pkt.track_descriptor.name = process_name
        else:
            pkt.track_descriptor.name = track_name

        self.pid2uuid[pid] = pkt.track_descriptor.uuid
        self.__uuid__ += 1
        self.__pid__ += 1
        
        # funnily enough, declaring a process and a track at the same time will get rid of the default track
        # if there is no trace in the track.  Unfortunately this changes the process track's name to "Process XXX"
        # so it shouldn't be applicable.
        # Instead, the only thing we can do is to assume a group to also accompany a track.

        #tid = self.__pid__
        #pkt.track_descriptor.thread.pid = pid
        #pkt.track_descriptor.thread.tid = tid
        #pkt.track_descriptor.thread.thread_name = process_name
        #self.__pid__ += 1
    
        self._flush_if_necessary()
        return Group(process_name, self, pid)

    def create_counter_track(self, track_name : str):
        """ Create a global counter track """
        return self._tid_packet(0, track_name, 1)

    def _flush_if_necessary(self):
        if len(self.trace.packet) > self.flush_threshold:
            self.flush()

    def _tid_packet(self, parent_pid, process_name, track_type):
        pkt = self.trace.packet.add()

        pkt.timestamp = 0
        pkt.trusted_packet_sequence_id = 2
        pkt.sequence_flags = 2
        pkt.track_descriptor.uuid = self.__uuid__
        tid = self.__pid__
        self.pid2uuid[self.__pid__] = self.__uuid__
        self.__uuid__ += 1
        self.__pid__ += 1
        pkt.track_descriptor.name = process_name

        if parent_pid != 0:
            pkt.track_descriptor.parent_uuid = self.pid2uuid[parent_pid]
    
        try:
            if track_type == 1:
                pkt.track_descriptor.counter.categories.append("dummy")
                return CounterTrack(process_name, self, tid)
            elif track_type == 0:
                return NormalTrack(process_name, self, tid)
            elif track_type == 2:
                return GroupTrack(process_name, self, tid)
            else:
                assert False
        finally:
            self._flush_if_necessary()
    
    def _get_iid_for(self, pkt, name):
        if name in self.interned_data:
            return self.interned_data[name]
    
        ev = pkt.interned_data.event_names.add()
        ev.name = name
        ev.iid = len(self.interned_data) + 1
    
        self.interned_data[name] = ev.iid
        return ev.iid

    def _add_debug_annotation_old(self, d, kwargs):
        for k,v in kwargs.items():
            assert(isinstance(k, str))

            x = d.add()
            x.name = k
            def set_single(x, v):
                if isinstance(v, str):
                    x.string_value = v
                elif isinstance(v, bool):
                    x.bool_value = v
                elif isinstance(v, int):
                    x.int_value = v
                elif isinstance(v, float):
                    x.double_value = v
                elif isinstance(v, dict):
                    # Try the older, deprecated version first.  If this doesn't work, use the code below (newer version)
                    def set_nested_dict(x, vv):
                        for k,v in vv.items():
                            x.dict_keys.append(k)
                            vt = x.dict_values.add()
                            set_single(vt, v)
                    set_nested_dict(x, v)
                    x.nested_type = pb2.DebugAnnotation.NestedValue.NestedType.DICT
                elif isinstance(v, list):
                    def set_nested_list(x, vv):
                        for v in vv:
                            vt = x.array_values.add()
                            set_single(vt, v)
                    set_nested_list(x, v)
                    x.nested_type = pb2.DebugAnnotation.NestedValue.NestedType.ARRAY
                else:
                    assert False

            if isinstance(v, dict) or isinstance(v, list):
                set_single(x.nested_value, v)
            else:
                set_single(x, v)

    def _add_debug_annotation_new(self, d, kwargs):
        for k,v in kwargs.items():
            assert(isinstance(k, str))

            x = d.add()
            x.name = k
            def set_single(x, v):
                if isinstance(v, str):
                    x.string_value = v
                elif isinstance(v, bool):
                    x.bool_value = v
                elif isinstance(v, int):
                    x.int_value = v
                elif isinstance(v, float):
                    x.double_value = v
                elif isinstance(v, dict):
                    self._add_debug_annotation_new(x.dict_entries, v)
                elif isinstance(v, list):
                    for vv in v:
                        set_single(x.array_values.add(), vv)
                else:
                    assert False
            set_single(x, v)

    def _add_debug_annotation(self, d, kwargs):
        return self._add_debug_annotation_new(d, kwargs)

        # some older perfettos (circa early 2021) don't support the new debug annotation packet type
        # in that case, enable this code below instead of the one above:

        # return self._add_debug_annotation_old(d, kwargs)

        # end code
     
    def _track_instant(self, pid, ts, annotation, kwargs, flow):
        pkt = self.trace.packet.add()

        uuid = self.pid2uuid[pid]
        pkt.timestamp = ts
        pkt.trusted_packet_sequence_id = 2
        pkt.sequence_flags = 2
        pkt.track_event.category_iids.append(1)
        pkt.track_event.type = pb2.TrackEvent.TYPE_INSTANT
        pkt.track_event.track_uuid = uuid
        pkt.track_event.name = annotation

        if kwargs is not None:
            self._add_debug_annotation(pkt.track_event.debug_annotations, kwargs)

        for x in flow:
            pkt.track_event.flow_ids.append(x)

        self._flush_if_necessary()
                   

    def _track_open(self, pid, ts, annotation, kwargs, flow):
        pkt = self.trace.packet.add()

        uuid = self.pid2uuid[pid]
    
        pkt.timestamp = ts
        pkt.track_event.name_iid = self._get_iid_for(pkt, annotation)
        pkt.trusted_packet_sequence_id = 2
        pkt.sequence_flags = 2
        pkt.track_event.category_iids.append(1)
        pkt.track_event.type = pb2.TrackEvent.TYPE_SLICE_BEGIN
        pkt.track_event.track_uuid = uuid

        if kwargs is not None:
            self._add_debug_annotation(pkt.track_event.debug_annotations, kwargs)
        for x in flow:
            pkt.track_event.flow_ids.append(x)

        self._flush_if_necessary()
        
    def _track_close(self, pid, ts, flow):
        pkt = self.trace.packet.add()

        uuid = self.pid2uuid[pid]
        pkt.trusted_packet_sequence_id = 2
        pkt.sequence_flags = 2
        pkt.timestamp = ts
        pkt.track_event.track_uuid = uuid
        pkt.track_event.type = pb2.TrackEvent.TYPE_SLICE_END
        for x in flow:
            pkt.track_event.flow_ids.append(x)

        self._flush_if_necessary()
    
    def _track_count(self, pid, ts, value):
        pkt = self.trace.packet.add()

        uuid = self.pid2uuid[pid]
        pkt.timestamp = ts
        pkt.trusted_packet_sequence_id = 2
        pkt.sequence_flags = 2
        pkt.track_event.type = pb2.TrackEvent.TYPE_COUNTER
        pkt.track_event.track_uuid = uuid
        pkt.track_event.counter_value = value

        self._flush_if_necessary()



