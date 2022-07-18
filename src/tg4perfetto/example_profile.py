import tg4perfetto
import threading

@tg4perfetto.trace_func_args
def merge(x, x1, x2):
    p1 = 0
    p2 = 0
    for p in range(len(x)):
        if p1 == len(x1):
            x[p] = x2[p2]
            p2 += 1
        elif p2 == len(x2):
            x[p] = x1[p1]
            p1 += 1
        elif x1[p1] > x2[p2]:
            x[p] = x2[p2]
            p2 += 1
        else:
            x[p] = x1[p1]
            p1 += 1
    return x

def merge_sort_wrapper(x, flow_id):
    tg4perfetto.instant("START_THREAD", incoming_flow_ids = [flow_id])
    return merge_sort(x)

def merge_sort_threaded(x):
    flow_ids = tg4perfetto.instant("INVOKE_THREAD", num_outgoing_flow_ids = 1)
    t = threading.Thread(target=merge_sort_wrapper, args=(x,flow_ids[0]))
    t.start()
    return (x, t)


count_stats = tg4perfetto.count("num_active_threads")

@tg4perfetto.trace_func
def merge_sort(x):
    l = len(x)

    if l < 4096: return sorted(x)

    if l < 40000:
        x1 = merge_sort(x[:int(l/2)])
        x2 = merge_sort(x[int(l/2):])
    else:
        count_stats.increment(1)
        x1, t1 = merge_sort_threaded(x[:int(l/2)])
        count_stats.increment(1)
        x2, t2 = merge_sort_threaded(x[int(l/2):])
        t1.join()
        count_stats.increment(-1)
        t2.join()
        count_stats.increment(-1)
    
    assert len(x1) + len(x2) == len(x)
    
    return merge(x, x1, x2)

if __name__ == "__main__":
    with tg4perfetto.open("xxx"):
        with tg4perfetto.trace('SORT').get_outgoing_flow_ids(1) as out_flow_id:
            xarray = [ (17 * x + 8) % 100 for x in range(100000) ]
            xarray = merge_sort(xarray)

            # Create one flow ID from the current track.  We can create flow IDs before closing the track.
            p = out_flow_id[0]

        # Set the incoming flow ID (optional, set only if there are any).
        with tg4perfetto.trace('VALIDATE').set_incoming_flow_ids([p]):
            tg4perfetto.instant("CHECKING", {"final_result": xarray})
            for i in range(len(xarray)-1):
                assert xarray[i] <= xarray[i+1]
            print("Done")
