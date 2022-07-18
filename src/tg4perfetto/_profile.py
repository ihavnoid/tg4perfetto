from ._core import _BaseTraceGenerator

import os
import sys
import functools
import threading
import time
from threading import local

_counter_tracks = {}
_tracefile = None
_tlock = threading.Lock()
_master_uuid = None
_my_uuid = None
_flow_id = 1

def open(filename): 
    global _tracefile, _master_uuid

    class X:
        def __init__(self):
            pass
        def __enter__(self):
            global _tracefile, _master_uuid, _my_uuid
            if _master_uuid is not None:
                raise AssertError("Nested trace opening not allowed")

            _tracefile = _BaseTraceGenerator(filename)
            pid = os.getpid()
            tid = threading.get_ident()
            uuid = _tracefile._pid_packet(pid, sys.argv[0], threading.current_thread().name)
            _master_uuid = uuid
            _my_uuid = local()
            _my_uuid.uuid = uuid
        def __exit__(self, type, value, traceback):
            global _tracefile, _master_uuid
            _tracefile = None
            _master_uuid = None
            _my_uuid = None

    return X()

def stop():
    _tracefile = None
    # We will leave _master_uuid set.  This is for detecting nested open calls.

def _create_thread_track_if_necessary():
    global _master_uuid, _my_uuid

    if hasattr(_my_uuid, "uuid"):
        return _my_uuid.uuid

    tid = threading.get_ident()
    _my_uuid.uuid = _tracefile._tid_packet(tid, _master_uuid, threading.current_thread().name, 0)
    
    return _my_uuid.uuid

def _create_counter_track_if_necessary(name):
    global _master_uuid, _counter_tracks, _tracefile
    if name not in _counter_tracks:
        # note that TID here is a dummy value (not really used)
        uuid = _tracefile._tid_packet(2**32 + len(_counter_tracks), _master_uuid, name, 1)
        _counter_tracks[name] = uuid
    return _counter_tracks[name]

class trace:
    def __init__(self, params, *kargs, **kwargs):
        self._params = params
        self._kargs = kargs
        self._kwargs = kwargs
        self._incoming_flow_ids = []
        self._outgoing_flow_ids = []

    def __enter__(self):
        global _tracefile,_tlock

        if _tracefile is not None:
            with _tlock:
                uuid = _create_thread_track_if_necessary()
                _tracefile._track_open(uuid, time.time_ns(), self._params, {"kargs":self._kargs, "kwargs":self._kwargs}, self._incoming_flow_ids)
        try:
            return self._outgoing_flow_ids
        finally:
            self._incoming_flow_ids = None

    def set_incoming_flow_ids(self, incoming_flow_ids):
        self._incoming_flow_ids += incoming_flow_ids
        return self

    def get_outgoing_flow_ids(self, num_outgoing_flow_ids):
        global _flow_id, _tlock
        with _tlock:
            self._outgoing_flow_ids = [x for x in range(_flow_id, _flow_id + num_outgoing_flow_ids)]
            _flow_id += num_outgoing_flow_ids

        return self

    def __exit__(self, type, value, traceback):
        global _flow_id, _tlock
        if _tracefile is not None:
            with _tlock:
                uuid = _create_thread_track_if_necessary()
                _tracefile._track_close(uuid, time.time_ns(), self._outgoing_flow_ids)
        self._flow_ids = None

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

def instant(name : str, description : dict = None, **kwargs):
    num_outgoing_flow_ids = kwargs.get("num_outgoing_flow_ids", 0)
    incoming_flow_ids = kwargs.get("incoming_flow_ids", [])
    global _tracefile, _tlock, _flow_id
    with _tlock:
        flow_ids = [x for x in range(_flow_id, _flow_id + num_outgoing_flow_ids)]
        _flow_id += num_outgoing_flow_ids
        if _tracefile is not None:
            uuid = _create_thread_track_if_necessary()
            _tracefile._track_instant(uuid, time.time_ns(), name, description, incoming_flow_ids + flow_ids)

    return flow_ids

class count:
    def __init__(self, name):
        self._name = name
        self._value = 0


    def count(self, value):
        global _tracefile

        with _tlock:
            self._value = value
            if _tracefile is not None:
                uuid = _create_counter_track_if_necessary(self._name)
                _tracefile._track_count(uuid, time.time_ns(), self.value)

    def increment(self, value):
        global _tracefile

        with _tlock:
            self._value += value
            if _tracefile is not None:
                uuid = _create_counter_track_if_necessary(self._name)
                _tracefile._track_count(uuid, time.time_ns(), self._value)
