import sys
from ._core import TraceGenerator

if __name__ == "__main__":
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

    # not necessary, but anyway.
    tgen.flush()
