#!/usr/bin/env python
"""Workload testing.

Test heavy transfer workloads over a single association to look for slowdowns
and memory leaks.

Results:
With heavy_workload_scp.py as the destination

01-03-2019: CTImageStorage x500 transferred in 44.05 s

With DCTMK's storescp as the destination

01-03-2019: CTImageStorage x500 transferred in 53.25 s
"""
#import cProfile
import logging
import os
import sys
import time

from pydicom import dcmread

#from dummy_c_scp import DummyStorageSCP
from pynetdicom import AE
from pynetdicom.sop_class import CTImageStorage, RTImageStorage

def init_yappi():
  OUT_FILE = '/home/dean/Coding/src/ascu.profile'

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
BIG_DATASET = dcmread(os.path.join(TEST_DS_DIR, 'RTImageStorage.dcm')) # 2.1 MB
DATASET = dcmread(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm')) # 39 kB

no_runs = 8
ds_per_run = 50

ae = AE()
ae.add_requested_context(CTImageStorage)
ae.add_requested_context(RTImageStorage)
assoc = ae.associate('localhost', 11112)

if assoc.is_established:
    print('Starting transfers...')
    results = []
    for ii in range(no_runs):
        start_time = time.time()
        for jj in range(ds_per_run):
            status = assoc.send_c_store(DATASET)
            if status.Status != 0x0000:
                print('C-STORE failed')
                assoc.release()
                sys.exit()
        end_time = time.time()
        delta_time = end_time - start_time
        results.append(delta_time)
        print('Run %d: %d/%d datasets in %.2f seconds' \
               %(ii + 1, ds_per_run + ii * ds_per_run,
                 no_runs * ds_per_run, delta_time))

    print('Transfers complete, releasing association.')
    assoc.release()
