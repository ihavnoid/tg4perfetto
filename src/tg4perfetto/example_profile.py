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

def merge_sort_threaded(x):
    t = threading.Thread(target=merge_sort, args=(x,))
    tg4perfetto.instant("INVOKE_THREAD")
    t.start()
    return (x, t)

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
    
    assert len(x1) + len(x2) == len(x)
    
    return merge(x, x1, x2)

if __name__ == "__main__":
    with tg4perfetto.open("xxx"):
        with tg4perfetto.trace('SORT'):
            xarray = [ (17 * x + 8) % 100 for x in range(100000) ]
            xarray = merge_sort(xarray)

        with tg4perfetto.trace('VALIDATE'):
            tg4perfetto.instant("CHECKING", {"final_result": xarray})
            for i in range(len(xarray)-1):
                assert xarray[i] <= xarray[i+1]
            print("Done")
