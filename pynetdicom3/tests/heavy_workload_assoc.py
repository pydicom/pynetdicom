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
"""

import logging
import os
import time

from pydicom import read_file

#from dummy_c_scp import DummyStorageSCP
from pynetdicom3 import AE
from pynetdicom3.sop_class import CTImageStorage, RTImageStorage

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)

TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
BIG_DATASET = read_file(os.path.join(TEST_DS_DIR, 'RTImageStorage.dcm')) # 2.1 MB
DATASET = read_file(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm')) # 39 kB

#scp = DummyStorageSCP(11112)
#scp.start()

no_runs = 400
ds_per_run = 1
results = []

ae = AE(scu_sop_class=[CTImageStorage, RTImageStorage])
print('Starting...')
for ii in range(no_runs):
    start_time = time.time()
    assoc = ae.associate('localhost', 11112)
    for jj in range(ds_per_run):
        if assoc.is_established:
            assoc.send_c_store(DATASET)
    assoc.release()
    end_time = time.time()
    delta_time = end_time - start_time
    results.append(delta_time)

total_time = 0.0
for result in results:
    total_time += result

print('Total time: %.2f seconds' %total_time)

#scp.stop()
