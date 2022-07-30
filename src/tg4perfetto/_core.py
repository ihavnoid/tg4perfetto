from . import perfetto_trace_pb2 as pb2

# Set this to true if you want to dump the protobuf results to stdout.  For debugging.
print_proto = False

class _BaseTraceGenerator:
    def __init__(self, filename : str):
        """ Create a trace """
        self.__uuid__ = 1234567
        self.interned_data = {}
        self.interned_source = {}
        self.flush_threshold = 10000
        self.list_max_size = 16

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
        if print_proto:
            print(self.trace)
        self.file.write(self.trace.SerializeToString())
        self.file.flush()
        self.trace = pb2.Trace()

    def __del__(self):
        self.flush()
        self.file.close()

    def _pid_packet(self, pid, process_name : str, track_name : str = None):
        """ Create a group.  Each "group" comes with a default normal track (named track_name)."""
        uuid = self.__uuid__
        pkt = self.trace.packet.add()
        pkt.timestamp = 0
        pkt.track_descriptor.uuid = uuid
        pkt.track_descriptor.process.pid = pid
        pkt.track_descriptor.process.process_name = process_name
        pkt.trusted_packet_sequence_id = 2
        pkt.sequence_flags = 2
        if track_name is None:
            pkt.track_descriptor.name = process_name
        else:
            pkt.track_descriptor.name = track_name

        self.__uuid__ += 1
        
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

        return uuid

    def _flush_if_necessary(self):
        if len(self.trace.packet) > self.flush_threshold:
            self.flush()

    def _tid_packet(self, my_pid, parent_uuid, process_name, track_type):
        pkt = self.trace.packet.add()

        pkt.timestamp = 0
        pkt.trusted_packet_sequence_id = 2
        pkt.sequence_flags = 2
        uuid = self.__uuid__

        pkt.track_descriptor.uuid = uuid
        self.__uuid__ += 1
        pkt.track_descriptor.name = process_name

        if parent_uuid != 0:
            pkt.track_descriptor.parent_uuid = parent_uuid
    
        if track_type == 1:
            pkt.track_descriptor.counter.categories.append("dummy")
        self._flush_if_necessary()

        return uuid
    
    def _get_iid_for(self, pkt, name):
        if name in self.interned_data:
            return self.interned_data[name]
    
        ev = pkt.interned_data.event_names.add()
        ev.name = name
        ev.iid = len(self.interned_data) + 1
    
        self.interned_data[name] = ev.iid
        return ev.iid

    def _add_debug_annotation(self, d, kwargs):
        cnt = 0
        for k,v in kwargs.items():
            cnt += 1
            x = d.add()
            if cnt == self.list_max_size:
                x.name = "..."
                x.string_value = "({} more items)".format(len(kwargs) - cnt)
                break

            x.name = str(k)
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
                    if len(v) == 0:
                        x.string_value = "[empty]"
                    else:
                        self._add_debug_annotation(x.dict_entries, v)
                elif isinstance(v, list) or isinstance(v, tuple):
                    if len(v) == 0:
                        x.string_value = "[empty]"
                    else:
                        for i,vv in zip(range(len(v)), v):
                            if i == self.list_max_size:
                                set_single(x.array_values.add(), "... ({} more items)".format(len(v) - i))
                                break
                            # for some reason, perfetto ui crashes on nested lists.
                            # add a dummy dictionary here
                            if isinstance(vv, list) or isinstance(vv, tuple):
                                vv = {"array" : vv}
                            set_single(x.array_values.add(), vv)
                elif hasattr(v, "__dict__"):
                    set_single(x, v.__dict__())
                else:
                    x.string_value = str(type(v))

            set_single(x, v)
     
    def _track_instant(self, uuid, ts, annotation, kwargs, flow, caller = None):
        pkt = self.trace.packet.add()

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

        if caller is not None:
            file,line,name = caller
            iid = self._get_source_iid_for(pkt, file, name, line)
            pkt.track_event.source_location_iid = iid

        self._flush_if_necessary()
                   

    def _get_source_iid_for(self, pkt, file, name, line):
        if (file, name, line) in self.interned_source:
            return self.interned_source[(file, name, line)]
        ev = pkt.interned_data.source_locations.add()
        ev.file_name = file
        ev.function_name = name
        ev.line_number = line
        ev.iid = len(self.interned_source) + 1
        self.interned_source[(file, name, line)] = ev.iid

        return ev.iid

    def _track_open(self, uuid, ts, annotation, kwargs, flow, caller = None):
        pkt = self.trace.packet.add()

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

        if caller is not None:
            file,line,name = caller
            iid = self._get_source_iid_for(pkt, file, name, line)
            pkt.track_event.source_location_iid = iid

        self._flush_if_necessary()
        
    def _track_close(self, uuid, ts, flow):
        pkt = self.trace.packet.add()

        pkt.trusted_packet_sequence_id = 2
        pkt.sequence_flags = 2
        pkt.timestamp = ts
        pkt.track_event.track_uuid = uuid
        pkt.track_event.type = pb2.TrackEvent.TYPE_SLICE_END
        for x in flow:
            pkt.track_event.flow_ids.append(x)

        self._flush_if_necessary()
    
    def _track_count(self, uuid, ts, value):
        pkt = self.trace.packet.add()

        pkt.timestamp = ts
        pkt.trusted_packet_sequence_id = 2
        pkt.sequence_flags = 2
        pkt.track_event.type = pb2.TrackEvent.TYPE_COUNTER
        pkt.track_event.track_uuid = uuid
        pkt.track_event.counter_value = value

        self._flush_if_necessary()

