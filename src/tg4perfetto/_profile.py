from ._core import _BaseTraceGenerator

import os
import sys
import functools
import threading
import time

_tracefile = None
_valid_tids = {}
_tlock = threading.Lock()
_master_uuid = None

def open(filename): 
    global _tracefile, _master_uuid

    class X:
        def __init__(self):
            pass
        def __enter__(self):
            global _tracefile, _master_uuid, _valid_tids
            if _master_uuid is not None:
                raise AssertError("Nested trace opening not allowed")

            _tracefile = _BaseTraceGenerator(filename)
            pid = os.getpid()
            tid = threading.get_ident()
            uuid = _tracefile._pid_packet(pid, sys.argv[0], threading.current_thread().name)
            _valid_tids[tid] = uuid
            _master_uuid = uuid

        def __exit__(self, type, value, traceback):
            global _tracefile, _master_uuid
            _tracefile = None
            _master_uuid = None

    return X()

def stop():
    _tracefile = None
    # We will leave _master_uuid set.  This is for detecting nested open calls.

def _create_thread_track_if_necessary():
    global _master_uuid

    tid = threading.get_ident()
    if tid in _valid_tids:
        return _valid_tids[tid]

    uuid = _tracefile._tid_packet(tid, _master_uuid, threading.current_thread().name, 0)
    _valid_tids[tid] = uuid
    
    return uuid

class trace:
    def __init__(self, params, *kargs, **kwargs):
        self._params = params
        self._kargs = kargs
        self._kwargs = kwargs

    def __enter__(self):
        global _tracefile,_tlock

        if _tracefile is not None:
            _tlock.acquire()
            uuid = _create_thread_track_if_necessary()
            _tracefile._track_open(uuid, time.time_ns(), self._params, {"kargs":self._kargs, "kwargs":self._kwargs}, [])
            _tlock.release()

    def __exit__(self, type, value, traceback):
        if _tracefile is not None:
            _tlock.acquire()
            uuid = _create_thread_track_if_necessary()
            _tracefile._track_close(uuid, time.time_ns(), [])
            _tlock.release()

def trace_func(func):
    @functools.wraps(func)
    def f(*kargs, **kwargs):
        with trace(func.__name__) as _:
            return func(*kargs, **kwargs)
    return f

def trace_func_args(func):
    @functools.wraps(func)
    def f(*kargs, **kwargs):
        with trace(func.__name__, *kargs, **kwargs) as _:
            return func(*kargs, **kwargs)
    return f

def instant(name : str, description : dict = None):
    global _tracefile, _tlock
    if _tracefile is not None:
        _tlock.acquire()
        uuid = _create_thread_track_if_necessary()
        _tracefile._track_instant(uuid, time.time_ns(), name, description, [])
        _tlock.release()
