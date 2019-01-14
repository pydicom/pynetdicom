#!/usr/bin/env python
"""Workload testing.

Test heavy transfer workloads over a single association to look for slowdowns
and memory leaks.

Results:
31-01-2016: CTImageStorage: 30 runs of 50 in 12.4 +/- 0.5 s/run (~59 MB)
            RTImageStorage: 30 runs of 50 in 138.1 +/- 3.5 s/run (~3.1 GB)
            Ratio data: 53.6; Ratio time/run: 11.1
17-03-2018: f7ba772 : (different hardware)
            CTImageStorage: 30 runs of 50 in 6.0 +/- 0.1 s/run (~59 MB)
            RTImageStorage: 30 runs of 50 in 70.8 +/- 0.4 s/run (~3.1 GB)
            Ratio time/run: 11.8
"""

import logging
import os
import time

from pydicom import read_file

from pynetdicom import AE
from pynetdicom import _config
from pynetdicom.sop_class import CTImageStorage, RTImageStorage

LOGGER = logging.getLogger('pynetdicom')
LOGGER.setLevel(logging.CRITICAL)

TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
BIG_DATASET = read_file(os.path.join(TEST_DS_DIR, 'RTImageStorage.dcm')) # 2.1 MB
DATASET = read_file(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm')) # 39 kB

# Do/don't decode the received dataset
_config.DECODE_STORE_DATASETS = False

ae = AE()
ae.add_supported_context(CTImageStorage)
scp = ae.start_server(('', 11112), block=False)

ae.add_requested_context(CTImageStorage)
ae.add_requested_context(RTImageStorage)
assoc = ae.associate('localhost', 11112)

if assoc.is_established:
    print('Starting transfers...')
    no_runs = 30
    ds_per_run = 50
    results = []
    for ii in range(no_runs):
        start_time = time.time()
        for jj in range(ds_per_run):
            assoc.send_c_store(DATASET)
        end_time = time.time()
        delta_time = end_time - start_time
        results.append(delta_time)
        print('Run %d: %d/%d datasets in %.2f seconds' \
               %(ii + 1, ds_per_run + ii * ds_per_run,
                 no_runs * ds_per_run, delta_time))

    print('Transfers complete, releasing association.')
    assoc.release()

scp.shutdown()
