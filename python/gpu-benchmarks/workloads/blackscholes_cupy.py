#!/usr/bin/python
import os
import math
import sys
import time
import scipy.special as ss
import numpy as np
import cupy as cp
import cupyx as cpx

sys.path.append("../../lib")
sys.path.append("../../pycomposer")
sys.path.append(".")

from sa.annotation import Backend
from mode import Mode

DEFAULT_SIZE = 1 << 2
DEFAULT_CPU = 1 << 13
DEFAULT_GPU = 1 << 26


def get_data(mode, size):
    # Inputs
    price = np.ones(size, dtype='float64') * 4.0
    strike = np.ones(size, dtype='float64') * 4.0
    t = np.ones(size, dtype='float64') * 4.0
    rate = np.ones(size, dtype='float64') * 4.0
    vol = np.ones(size, dtype='float64') * 4.0
    return price, strike, t, rate, vol


def _get_tmp_arrays_cuda(size):
    # Tmp arrays
    tmp = cp.empty(size, dtype='float64')
    vol_sqrt = cp.empty(size, dtype='float64')
    rsig = cp.empty(size, dtype='float64')
    d1 = cp.empty(size, dtype='float64')
    d2 = cp.empty(size, dtype='float64')

    # Outputs
    call = cp.empty(size, dtype='float64')
    put = cp.empty(size, dtype='float64')
    return tmp, vol_sqrt, rsig, d1, d2, call, put


def get_tmp_arrays(mode, size):
    if mode == Mode.CUDA:
        return _get_tmp_arrays_cuda(size)

    # Tmp arrays
    tmp = np.empty(size, dtype='float64')
    vol_sqrt = np.empty(size, dtype='float64')
    rsig = np.empty(size, dtype='float64')
    d1 = np.empty(size, dtype='float64')
    d2 = np.empty(size, dtype='float64')

    # Outputs
    call = np.empty(size, dtype='float64')
    put = np.empty(size, dtype='float64')
    return tmp, vol_sqrt, rsig, d1, d2, call, put


def run_naive(price, strike, t, rate, vol, tmp, vol_sqrt, rsig, d1, d2, call, put):
    c05 = 3.0
    c10 = 1.5
    invsqrt2 = 1.0 / math.sqrt(2.0)

    np.multiply(vol, vol, out=rsig)
    np.multiply(rsig, c05, out=rsig)
    np.add(rsig, rate, out=rsig)

    np.sqrt(t, out=vol_sqrt)
    np.multiply(vol_sqrt, vol, out=vol_sqrt)

    np.multiply(rsig, t, out=tmp)
    np.divide(price, strike, out=d1)
    np.log2(d1, out=d1)
    np.add(d1, tmp, out=d1)

    np.divide(d1, vol_sqrt, out=d1)
    np.subtract(d1, vol_sqrt, out=d2)

    # d1 = c05 + c05 * erf(d1 * invsqrt2)
    np.multiply(d1, invsqrt2, out=d1)
    ss.erf(d1, out=d1)
    np.multiply(d1, c05, out=d1)
    np.add(d1, c05, out=d1)

    # d2 = c05 + c05 * erf(d2 * invsqrt2)
    np.multiply(d2, invsqrt2, out=d2)
    ss.erf(d2, out=d2)
    np.multiply(d2, c05, out=d2)
    np.add(d2, c05, out=d2)

    # Reuse existing buffers
    e_rt = vol_sqrt
    tmp2 = rsig

    # e_rt = exp(-rate * t)
    np.multiply(rate, -1.0, out=e_rt)
    np.multiply(e_rt, t, out=e_rt)
    np.exp(e_rt, out=e_rt)

    # call = price * d1 - e_rt * strike * d2
    #
    # tmp = price * d1
    # tmp2 = e_rt * strike * d2
    # call = tmp - tmp2
    np.multiply(price, d1, out=tmp)
    np.multiply(e_rt, strike, out=tmp2)
    np.multiply(tmp2, d2, out=tmp2)
    np.subtract(tmp, tmp2, out=call)

    # put = e_rt * strike * (c10 - d2) - price * (c10 - d1)
    # tmp = e_rt * strike
    # tmp2 = (c10 - d2)
    # put = tmp - tmp2
    # tmp = c10 - d1
    # tmp = price * tmp
    # put = put - tmp
    np.multiply(e_rt, strike, out=tmp)
    np.subtract(c10, d2, out=tmp2)
    np.multiply(tmp, tmp2, out=put)
    np.subtract(c10, d1, out=tmp)
    np.multiply(price, tmp, out=tmp)
    np.subtract(put, tmp, out=put)
    return call, put


def run_cuda(price, strike, t, rate, vol, tmp, vol_sqrt, rsig, d1, d2, call, put):
    t = time.time()
    price = cp.array(price)
    strike = cp.array(strike)
    t = cp.array(t)
    rate = cp.array(rate)
    vol = cp.array(vol)
    print('Transfer inputs:', time.time() - t)

    c05 = 3.0
    c10 = 1.5
    invsqrt2 = 1.0 / math.sqrt(2.0)

    t = time.time()
    cp.multiply(vol, vol, out=rsig)
    cp.multiply(rsig, c05, out=rsig)
    cp.add(rsig, rate, out=rsig)

    cp.sqrt(t, out=vol_sqrt)
    cp.multiply(vol_sqrt, vol, out=vol_sqrt)

    cp.multiply(rsig, t, out=tmp)
    cp.divide(price, strike, out=d1)
    cp.log2(d1, out=d1)
    cp.add(d1, tmp, out=d1)

    cp.divide(d1, vol_sqrt, out=d1)
    cp.subtract(d1, vol_sqrt, out=d2)

    # d1 = c05 + c05 * erf(d1 * invsqrt2)
    cp.multiply(d1, invsqrt2, out=d1)
    d1 = cp.asnumpy(d1)
    ss.erf(d1, out=d1)
    d1 = cp.array(d1)
    cp.multiply(d1, c05, out=d1)
    cp.add(d1, c05, out=d1)

    # d2 = c05 + c05 * erf(d2 * invsqrt2)
    cp.multiply(d2, invsqrt2, out=d2)
    d2 = cp.asnumpy(d2)
    ss.erf(d2, out=d2)
    d2 = cp.array(d2)
    cp.multiply(d2, c05, out=d2)
    cp.add(d2, c05, out=d2)

    # Reuse existing buffers
    e_rt = vol_sqrt
    tmp2 = rsig

    # e_rt = exp(-rate * t)
    cp.multiply(rate, -1.0, out=e_rt)
    cp.multiply(e_rt, t, out=e_rt)
    cp.exp(e_rt, out=e_rt)

    # call = price * d1 - e_rt * strike * d2
    #
    # tmp = price * d1
    # tmp2 = e_rt * strike * d2
    # call = tmp - tmp2
    cp.multiply(price, d1, out=tmp)
    cp.multiply(e_rt, strike, out=tmp2)
    cp.multiply(tmp2, d2, out=tmp2)
    cp.subtract(tmp, tmp2, out=call)

    # put = e_rt * strike * (c10 - d2) - price * (c10 - d1)
    # tmp = e_rt * strike
    # tmp2 = (c10 - d2)
    # put = tmp - tmp2
    # tmp = c10 - d1
    # tmp = price * tmp
    # put = put - tmp
    cp.multiply(e_rt, strike, out=tmp)
    cp.subtract(c10, d2, out=tmp2)
    cp.multiply(tmp, tmp2, out=put)
    cp.subtract(c10, d1, out=tmp)
    cp.multiply(price, tmp, out=tmp)
    cp.subtract(put, tmp, out=put)
    print('Compute:', time.time() - t)

    t = time.time()
    call = cp.asnumpy(call)
    put = cp.asnumpy(put)
    print('Transfer outputs:', time.time() - t)
    return call, put


def run(mode, size=None, cpu=None, gpu=None, threads=None):
    # Optimal defaults
    if size == None:
        size = DEFAULT_SIZE
    if cpu is None:
        cpu = DEFAULT_CPU
    if gpu is None:
        gpu = DEFAULT_GPU
    if threads is None:
        if mode == Mode.MOZART:
            threads = 16
        else:
            threads = 1

    batch_size = {
        Backend.CPU: cpu,
        Backend.GPU: gpu,
    }

    start = time.time()
    inputs = get_data(mode, size)
    print('Inputs (doesn\'t count):', time.time() - start)

    # Get inputs
    start = time.time()
    tmp_arrays = get_tmp_arrays(mode, size)
    init_time = time.time() - start
    print('Initialization:', init_time)

    start = time.time()
    if mode.is_composer():
        call, put = run_composer(mode, *inputs, *tmp_arrays, batch_size, threads)
    elif mode == Mode.NAIVE:
        call, put = run_naive(*inputs, *tmp_arrays)
    elif mode == Mode.CUDA:
        call, put = run_cuda(*inputs, *tmp_arrays)
    else:
        raise ValueError
    runtime = time.time() - start

    print('Runtime:', runtime)
    sys.stdout.write('Total: {}\n'.format(init_time + runtime))
    sys.stdout.flush()
    print(call)
    print(put)
    return init_time, runtime