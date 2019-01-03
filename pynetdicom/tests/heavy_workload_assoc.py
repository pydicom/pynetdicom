#!/usr/bin/env python
"""Workload testing.

Test heavy transfer workloads over a multiple associations to look for slowdowns
and memory leaks.

Results:
17-03-2018:
            1 association of 400 datasets 68.34 s
            400 associations of 1 dataset 200.7 s
17-03-2018: 6fe488a
            1 association of 400 datasets 79.3 s
            400 associations of 1 dataset 200.5 s

With heavy_workload_scp as the destination

01-03-2019: 400 associations of 1 dataset 84.7 s

With storescp as the destination

01-03-2019: 400 associations of 1 dataset 48.8 s
"""

import logging
import os
import sys
import time

from pydicom import dcmread

#from dummy_c_scp import DummyStorageSCP
from pynetdicom import AE
from pynetdicom.sop_class import CTImageStorage, RTImageStorage

def init_yappi():
  OUT_FILE = '/home/dean/Coding/src/assoc.profile'

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

TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
BIG_DATASET = dcmread(os.path.join(TEST_DS_DIR, 'RTImageStorage.dcm')) # 2.1 MB
DATASET = dcmread(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm')) # 39 kB

no_runs = 400
ds_per_run = 1
results = []

ae = AE()
ae.add_requested_context(CTImageStorage)
ae.add_requested_context(RTImageStorage)
print('Starting...')
for ii in range(no_runs):
    start_time = time.time()
    assoc = ae.associate('localhost', 11112)
    for jj in range(ds_per_run):
        if assoc.is_established:
            status = assoc.send_c_store(DATASET)
            if status.Status != 0x0000:
                print('C-STORE failed')
                assoc.release()
                sys.exit()
            assoc.release()

    end_time = time.time()
    delta_time = end_time - start_time
    results.append(delta_time)

total_time = 0.0
for result in results:
    total_time += result

print('Total time: %.2f seconds' %total_time)
