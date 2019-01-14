#!/usr/bin/env python
"""Workload testing.

Test heavy transfer workloads over a single association to look for slowdowns
and memory leaks.

Results:
31-01-2016: CTImageStorage: 30 runs of 50 in 12.4 +/- 0.5 s/run (~59 MB)
            RTImageStorage: 30 runs of 50 in 138.1 +/- 3.5 s/run (~3.1 GB)
            Ratio data: 53.6; Ratio time/run: 11.1
"""
import cProfile
import logging
import os
import time
import threading

from pydicom import read_file

from dummy_c_scp import DummyStorageSCP
from pynetdicom import AE
from pynetdicom import _config
from pynetdicom.sop_class import CTImageStorage, RTImageStorage


def init_yappi():
  OUT_FILE = '/home/dean/Coding/src/scp.assoc'

  import atexit
  import yappi

  print('[YAPPI START]')
  yappi.set_clock_type('wall')
  yappi.start()

  @atexit.register
  def finish_yappi():
    yappi.stop()

    print('[YAPPI WRITE]')

    stats = yappi.get_func_stats()

    # 'ystat' is Yappi internal format
    for stat_type in ['pstat', 'callgrind']:
      print('writing {}.{}'.format(OUT_FILE, stat_type))
      stats.save('{}.{}'.format(OUT_FILE, stat_type), type=stat_type)

    print('\n[YAPPI FUNC_STATS]')

    print('writing {}.func_stats'.format(OUT_FILE))
    with open('{}.func_stats'.format(OUT_FILE), 'wb') as fh:
      stats.print_all(out=fh)

    print('\n[YAPPI THREAD_STATS]')

    print('writing {}.thread_stats'.format(OUT_FILE))
    tstats = yappi.get_thread_stats()
    with open('{}.thread_stats'.format(OUT_FILE), 'wb') as fh:
      tstats.print_all(out=fh)

    print('[YAPPI DONE]')


#init_yappi()


LOGGER = logging.getLogger('pynetdicom')
LOGGER.setLevel(logging.CRITICAL)
#LOGGER.setLevel(logging.DEBUG)

TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
BIG_DATASET = read_file(os.path.join(TEST_DS_DIR, 'RTImageStorage.dcm')) # 2.1 MB
DATASET = read_file(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm')) # 39 kB


_config.DECODE_STORE_DATASETS = True


def on_c_store(ds, context, info):
    """Callback for ae.on_c_store"""
    return 0x0000


ae = AE()
ae.add_supported_context(CTImageStorage)
ae.add_supported_context(RTImageStorage)

ae.on_c_store = on_c_store

ae.start_server(('', 11112))
