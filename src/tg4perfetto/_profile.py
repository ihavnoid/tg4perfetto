from ._core import _BaseTraceGenerator

import typing
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
_flow_id = 1
_all_tracks = []
_tls = local()

def _create_counter_track_if_necessary(name):
    global _master_uuid, _counter_tracks, _tracefile
    if name not in _counter_tracks:
        # note that TID here is a dummy value (not really used)
        uuid = _tracefile._tid_packet(2**32 + len(_counter_tracks), _master_uuid, name, 1)
        _counter_tracks[name] = uuid
    return _counter_tracks[name]

class _trace:
    def __init__(self, uuid, params, *kargs, **kwargs):
        self._params = params
        self._kargs = kargs
        self._kwargs = kwargs
        self._incoming_flow_ids = []
        self._outgoing_flow_ids = []
        self._uuid = uuid
        self._caller = None
    def set_caller(self, caller):
        if _tracefile is not None:
            if isinstance(caller, tuple):
                self._caller = caller
            elif isinstance(caller, typing.Callable):
                self._caller = (caller.__code__.co_filename, caller.__code__.co_firstlineno, caller.__code__.co_name)
        return self

    def __enter__(self):
        global _tracefile,_tlock

        if _tracefile is not None:
            if self._caller is None:
                import inspect
                frame = inspect.currentframe().f_back
                self._caller = frame.f_code.co_filename, frame.f_lineno, frame.f_code.co_name
            if self._uuid is not None:
                with _tlock:
                    _tracefile._track_open(self._uuid, time.time_ns(), self._params, {"kargs":self._kargs, "kwargs":self._kwargs}, self._incoming_flow_ids, self._caller)
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
            if self._uuid is not None:
                with _tlock:
                    _tracefile._track_close(self._uuid, time.time_ns(), self._outgoing_flow_ids)
        self._flow_ids = None


class track:
    def __init__(self, name):
        self._name = name
        self._uuid = None

    def trace(self, param, *kargs, **kwargs):
        global _master_uuid

        if _tracefile is not None:
            with _tlock:
                # tid isn't really used here
                self._uuid = _tracefile._tid_packet(0, _master_uuid, self._name, 0)

        ret = _trace(self._uuid, param, *kargs, **kwargs)
        return ret
        
    def instant(self, name, description : dict = None, **kwargs):
        return self._instant(name, description, **kwargs)

    def _instant(self, name, description : dict = None, **kwargs):
        num_outgoing_flow_ids = kwargs.get("num_outgoing_flow_ids", 0)
        incoming_flow_ids = kwargs.get("incoming_flow_ids", [])
        global _tracefile, _tlock, _flow_id, _master_uuid
        with _tlock:
            flow_ids = [x for x in range(_flow_id, _flow_id + num_outgoing_flow_ids)]
            _flow_id += num_outgoing_flow_ids
            if _tracefile is not None:
                import inspect

                frame = inspect.currentframe().f_back.f_back
                caller = frame.f_code.co_filename, frame.f_lineno, frame.f_code.co_name
                if self._uuid is None:
                    self._uuid = _tracefile._tid_packet(0, _master_uuid, self._name, 0)
                _tracefile._track_instant(self._uuid, time.time_ns(), name, description, incoming_flow_ids + flow_ids, caller)
    
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

def trace(params, *kargs, **kwargs):
    if not hasattr(_tls, "default_track"):
        _tls.default_track = track(threading.current_thread().name)
    return _tls.default_track.trace(params, *kargs, **kwargs)

def instant(name : str, description : dict = None, **kwargs):
    if not hasattr(_tls, "default_track"):
        _tls.default_track = track(threading.current_thread().name)
    return _tls.default_track._instant(name, description, **kwargs)

def trace_func(x):
    if isinstance(x, typing.Callable):
        func = x
        @functools.wraps(func)
        def f(*kargs, **kwargs):
            with trace(func.__name__).set_caller(func) as _:
                return func(*kargs, **kwargs)
        return f
    elif isinstance(x, track):
        tobj = x
        def trace_func_wrapper(func):
            nonlocal tobj
            @functools.wraps(func)
            def f(*kargs, **kwargs):
                nonlocal tobj
                with tobj.trace(func.__name__).set_caller(func) as _:
                    return func(*kargs, **kwargs)
            return f
        return trace_func_wrapper
    else:
        assert False

def trace_func_args(x):
    if isinstance(x, typing.Callable):
        func = x
        @functools.wraps(func)
        def f(*kargs, **kwargs):
            with trace(func.__name__, *kargs, **kwargs).set_caller(func) as _:
                return func(*kargs, **kwargs)
        return f
    elif isinstance(x, track):
        tobj = x
        def tarce_func_wrapper(func):
            nonlocal tobj
            @functools.wraps(func)
            def f(*kargs, **kwargs):
                nonlocal tobj
                with tobj.trace(func.__name__, *kargs, **kwargs).set_caller(func) as _:
                    return func(*kargs, **kwargs)
            return f
        return trace_func_wrapper

def open(filename): 
    global _tracefile, _master_uuid

    class X:
        def __init__(self):
            pass
        def __enter__(self):
            global _tracefile, _master_uuid
            if _master_uuid is not None:
                raise AssertError("Nested trace opening not allowed")

            _tracefile = _BaseTraceGenerator(filename)
            pid = os.getpid()
            tid = threading.get_ident()
            uuid = _tracefile._pid_packet(pid, sys.argv[0], threading.current_thread().name)
            _master_uuid = uuid
        def __exit__(self, type, value, traceback):
            global _tracefile, _master_uuid
            _tracefile = None
            _master_uuid = None

    return X()

def stop():
    _tracefile = None
    # We will leave _master_uuid set.  This is for detecting nested open calls.

