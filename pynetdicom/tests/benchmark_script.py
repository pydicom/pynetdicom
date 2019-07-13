#!/usr/bin/env python
"""Benchmarking script for pynetdicom.

Overall transfer speed (no datasets written to file unless noted)
* pynetdicom as SCP, DCMTK's storescu as SCU
  * 1000 datasets over 1 association
  * 1000 datasets over 1 association (datasets written to temp file)
  * 1 dataset per association over 1000 sequential associations
  * 1000 datasets per association over 10 simulataneous associations
* pynetdicom as SCU, DCMTK's storescp as SCP
  * 1000 datasets over 1 association
  * 1 dataset per association for 1000 sequential associations

"""

from datetime import datetime
import multiprocessing
import os
import subprocess
import tempfile
import time

from pydicom import dcmread
from pydicom.uid import ImplicitVRLittleEndian

from pynetdicom import AE, evt, build_context, debug_logger


#debug_logger()


TEST_DS_DIR = os.path.join(os.path.dirname(__file__), '..', 'dicom_files')
#DATASET = dcmread(os.path.join(TEST_DS_DIR, 'RTImageStorage.dcm')) # 2.1 MB
DATASET = dcmread(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm')) # 39 kB


def init_yappi():
    """Initialise the profiler."""
    timestamp = datetime.now()
    timestamp = timestamp.strftime("%Y%m%d%H%M%S")
    OUT_FILE = '{}.profile'.format(timestamp)

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
        with open('{}.func_stats'.format(OUT_FILE), 'w') as fh:
            stats.print_all(out=fh)

        print('\n[YAPPI THREAD_STATS]')

        print('writing {}.thread_stats'.format(OUT_FILE))
        tstats = yappi.get_thread_stats()
        with open('{}.thread_stats'.format(OUT_FILE), 'w') as fh:
            tstats.print_all(out=fh)

        print('[YAPPI DONE]')


def which(program):
    # Determine if a given program is installed on PATH
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file


def start_storescp():
    """Start DCMTK's storescp in a background process.

    Returns
    -------
    subprocess.Popen
        The running process.
    """
    args = [which('storescp'), '--ignore', '11112']
    return subprocess.Popen(args)


def start_storescu(ds_per_assoc):
    """Run DCMTK's storescu in a background process.

    Parameters
    ----------
    ds_per_assoc : int
        The number of datasets to send using `storescu`.
    """
    fpath = os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm')
    args = [which('storescu'), 'localhost', '11112'] + [fpath] * ds_per_assoc
    return subprocess.Popen(args)


def receive_store(nr_assoc, ds_per_assoc, write_ds=False, use_yappi=False):
    """Run a Storage SCP and transfer datasets with sequential storescu's.

    Parameters
    ----------
    nr_assoc : int
        The total number of (sequential) associations that will be made.
    ds_per_assoc : int
        The number of C-STORE requests sent per successful association.
    write_ds : bool, optional
        True to write the received dataset to file, False otherwise (default).
    use_yappi : bool, optional
        True to use the yappi profiler, False otherwise (default).
    """
    if use_yappi:
        init_yappi()

    def handle(event):
        if write_ds:
            # TODO: optimise write using event.request.DataSet instead
            # Standard write using dataset decode and re-encode
            tfile = tempfile.TemporaryFile(mode='w+b')
            ds = event.dataset
            ds.file_meta = event.file_meta
            ds.save_as(tfile)

        return 0x0000

    ae = AE()
    ae.acse_timeout = 5
    ae.dimse_timeout = 5
    ae.network_timeout = 5
    ae.add_supported_context(DATASET.SOPClassUID, ImplicitVRLittleEndian)

    server = ae.start_server(
        ('', 11112), block=False, evt_handlers=[(evt.EVT_C_STORE, handle)]
    )

    time.sleep(0.5)

    start_time = time.time()
    run_times = []

    is_successful = True

    for ii in range(nr_assoc):
        p = start_storescu(ds_per_assoc)
        # Block until transfer is complete
        p.wait()
        if p.returncode != 0:
            is_successful = False
            break

    if is_successful:
        print(
            "C-STORE SCP transferred {} total datasets over {} "
            "association(s) in {:.2f} s"
            .format(nr_assoc * ds_per_assoc, nr_assoc, time.time() - start_time)
        )
    else:
        print("C-STORE SCP benchmark failed")

    server.shutdown()


def receive_store_simultaneous(nr_assoc, ds_per_assoc, use_yappi=False):
    """Run a Storage SCP and transfer datasets with simultaneous storescu's.

    Parameters
    ----------
    nr_assoc : int
        The number of simultaneous associations that will be made.
    ds_per_assoc : int
        The number of C-STORE requests sent per successful association.
    use_yappi : bool, optional
        True to use the yappi profiler, False otherwise (default).
    """
    if use_yappi:
        init_yappi()

    def handle(event):
        return 0x0000

    ae = AE()
    ae.acse_timeout = 5
    ae.dimse_timeout = 5
    ae.network_timeout = 5
    ae.maximum_associations = 15
    ae.add_supported_context(DATASET.SOPClassUID, ImplicitVRLittleEndian)

    server = ae.start_server(
        ('', 11112), block=False, evt_handlers=[(evt.EVT_C_STORE, handle)]
    )

    time.sleep(0.5)

    start_time = time.time()
    run_times = []

    is_successful = True

    processes = []
    for ii in range(nr_assoc):
        processes.append(start_storescu(ds_per_assoc))

    while None in [pp.poll() for pp in processes]:
        pass

    returncodes = list(set([pp.returncode for pp in processes]))
    if len(returncodes) != 1 or returncodes[0] != 0:
        is_successful = False

    if is_successful:
        print(
            "C-STORE SCP transferred {} total datasets over {} "
            "association(s) in {:.2f} s"
            .format(nr_assoc * ds_per_assoc, nr_assoc, time.time() - start_time)
        )
    else:
        print("C-STORE SCP benchmark failed")

    server.shutdown()


def send_store(nr_assoc, ds_per_assoc, use_yappi=False):
    """Send a number of sequential C-STORE requests.

    Parameters
    ----------
    nr_assoc : int
        The total number of (sequential) associations that will be made.
    ds_per_assoc : int
        The number of C-STORE requests sent per successful association.
    use_yappi : bool, optional
        True to use the yappi profiler, False otherwise (default).
    """
    if use_yappi:
        init_yappi()

    # Start SCP
    server = start_storescp()
    time.sleep(0.5)

    ae = AE()
    ae.acse_timeout = 5
    ae.dimse_timeout = 5
    ae.network_timeout = 5
    ae.add_requested_context(DATASET.SOPClassUID, ImplicitVRLittleEndian)

    # Start timer
    start_time = time.time()
    run_times = []

    is_successful = True

    for ii in range(nr_assoc):
        if not is_successful:
            break

        assoc = ae.associate('localhost', 11112)

        if assoc.is_established:
            for jj in range(ds_per_assoc):
                try:
                    status = assoc.send_c_store(DATASET)
                    if status and status.Status != 0x0000:
                        is_successful = False
                        break
                except RuntimeError:
                    is_successful = False
                    break

            assoc.release()
            if is_successful:
                run_times.append(time.time() - start_time)
        else:
            is_successful = False
            break

    if is_successful:
        print(
            "C-STORE SCU transferred {} total datasets over {} "
            "association(s) in {:.2f} s"
            .format(nr_assoc * ds_per_assoc, nr_assoc, time.time() - start_time)
        )
    else:
        print("C-STORE SCU benchmark failed")

    server.terminate()


if __name__ == "__main__":
    print("Use yappi (y/n:)")
    use_yappi = input()
    if use_yappi in ['y', 'Y']:
        use_yappi = True
    else:
        use_yappi = False

    print("Which benchmark do you wish to run?")
    print("  1. Storage SCU, 1000 datasets over 1 association")
    print("  2. Storage SCU, 1 dataset per association over 1000 associations")
    print("  3. Storage SCP, 1000 datasets over 1 association")
    print("  4. Storage SCP, 1000 datasets over 1 association (write)")
    print("  5. Storage SCP, 1 dataset per association over 1000 associations")
    print("  6. Storage SCP, 1000 dataset per association over 10 simultaneous associations")
    bench_index = input()

    if bench_index == "1":
        send_store(1, 1000, use_yappi)
    elif bench_index == "2":
        send_store(1000, 1, use_yappi)
    elif bench_index == "3":
        receive_store(1, 1000, False, use_yappi)
    elif bench_index == "4":
        receive_store(1, 1000, True, use_yappi)
    elif bench_index == "5":
        receive_store(1000, 1, False, use_yappi)
    elif bench_index == "6":
        receive_store_simultaneous(10, 1000, use_yappi)
