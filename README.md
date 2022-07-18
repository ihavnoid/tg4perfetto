# tg4perfetto
Simple python library for generating your own perfetto traces for your application.  This is not an app instrumentation library!


## Python application tracing
Example code (see tg4perfetto/example_profile.py for the code)
    import tg4perfetto
    import threading
    
    # Trace function, and records function args
    # (careful, this can be quite huge)
    @tg4perfetto.trace_func_args
    def merge(x, x1, x2):
        # omitted here
    
    def merge_sort_wrapper(x, flow_id):
        tg4perfetto.instant("START_THREAD", incoming_flow_ids = [flow_id])
        return merge_sort(x)

    def merge_sort_threaded(x):
        flow_ids = tg4perfetto.instant("INVOKE_THREAD", num_outgoing_flow_ids = 1)
        t = threading.Thread(target=merge_sort_wrapper, args=(x,flow_ids[0]))
        t.start()
        return (x, t)
    
    # Trace function call, don't record function args
    @tg4perfetto.trace_func
    def merge_sort(x):
        l = len(x)
        if l < 4096: return sorted(x)
        if l < 40000:
            x1 = merge_sort(x[:int(l/2)])
            x2 = merge_sort(x[int(l/2):])
        else:
            x1, t1 = merge_sort_threaded(x[:int(l/2)])
            x2, t2 = merge_sort_threaded(x[int(l/2):])
            t1.join()
            t2.join()
        return merge(x, x1, x2)
    
    if __name__ == "__main__":
        # Trace capture is running until we exit scope of this "with" statement
        with tg4perfetto.open("xxx.perfetto-trace"):

            # Creates a "custom" track
            with tg4perfetto.trace('SORT').get_outgoing_flow_ids(1) as out_flow_id:
                xarray = [ (17 * x + 8) % 100 for x in range(100000) ]
                xarray = merge_sort(xarray)
                p = out_flow_id[0]
    
            with tg4perfetto.trace('VALIDATE').set_incoming_flow_ids([p]):
                # Instant event which is marked as an "arrow" on perfetto
                tg4perfetto.instant("CHECKING", {"final_result": xarray})
                for i in range(len(xarray)-1):
                    assert xarray[i] <= xarray[i+1]
                print("Done")

This will generate a trace file named "xxx.perfetto-trace" which can be read from perfetto.

## Custom packet generation
Example code (see tg4perfetto/example.py for the code)

    # Packets can be created out-of-order.  This is because perfetto is designed to process out-of-order traces
    # and reads all packets at once, rearranges them, and then visualizes it at once.
    tgen = TraceGenerator(sys.argv[1])
    pid = tgen.create_group("aaa", "example_track")
    pid.open(100, "SOME_TRACK")
    # "Flow" packet.  this will create an arrow from here to "open" event down there (400ns)
    pid.close(250, [4])

    # Global counter track
    tid = tgen.create_counter_track("bbb")
    tid.count(0, 3)
    tid.count(200, 5)
    tid.count(400, 7)
    tid.count(700, 2)

    # Counter track within the "aaa" group"
    tid = pid.create_counter_track("bbb")
    tid.count(0, 2)
    tid.count(200, 4)
    tid.count(400, 5)
    tid.count(700, 1)

    tid = pid.create_track("ddd")
    tid.open(100, "WXX")
    # another "flow" packet.
    tid.close(300, [3])

    tgen.flush()

    pid = tgen.create_group("vvv")
    tid = pid.create_counter_track("bbb2")
    tid.count(0, 2)
    tid.count(300, 400)
    tid.count(400, 500)
    tid.count(700, 1000)

    tid = pid.create_track("ddd2")
    tid2 = pid.create_track("ddd3")

    tid2.instant(200, "WXYZ")
    tid.open(222, "XXX")
    tid2.open(300, "WXX3", {"aaa":"bbb", "ccc":"ddd"})
    tid2.instant(300, "ABCDE", {"aaa": "bbb", "ccc": "xxx"})
    tid.close(333)
    # receives an arrow from the packet above.  this can be either from an instant event or a normal event.
    tid2.open(400, "WXX4", {"aaa":"bbb", "ccc":"ddd"}, [3, 4])
    tid2.instant(400, "ABCDE")

    # Some annotation on instant event
    tid2.instant(600, "ADE", {"aaa": "abc", "ccc": "xxx", "eee" : {"aaa": "abc", "ccc": "ddd"}})
    tid2.close(670, [2])

    # very complex annotations!
    tid2.instant(700, "ADE2", {
        "aaa": "abc",
        "ccc": [1, 2, 3, 4, "a", "b", {"abcdef" : "fdsa", "ggg": True}],
        "eee" : {
            "aaa": "abc",
            "ccc": True,
            "eee": {
                "fff": "ggg",
                "hhh": 0x1234567
            }
        },
        "jjj": "kkk"
    }, [2])
    tid2.close(900, [1])
    tid.open(900, "WXX2", {"aaa":"bbb", "ccc":"ddd"}, [1])
    tid.close(1000)

    pid4 = tgen.create_group("abc.2")
    tid4 = pid4.create_group("XX")
    t1 = tid4.create_track()
    t2 = tid4.create_track()
    t1.open(100, "X")
    t2.open(300, "Y")
    t1.close(500)
    t2.close(600)


Example output:

![Example screenshot](screenshot.png)
