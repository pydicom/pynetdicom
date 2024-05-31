#!/usr/bin/env python
"""Benchmarking script for pynetdicom.

Overall transfer speed (no datasets written to file unless noted)
* pynetdicom as SCP, DCMTK's storescu as SCU
  * 1000 datasets over 1 association
  * 1000 datasets over 1 association (datasets written to temp file)
  * 1 dataset per association over 1000 sequential associations
  * 1000 datasets per association over 10 simultaneous associations
* pynetdicom as SCU, DCMTK's storescp as SCP
  * 1000 datasets over 1 association
  * 1 dataset per association for 1000 sequential associations

"""

from datetime import datetime
import os
import re
import subprocess
import tempfile
import time

from pydicom import dcmread
from pydicom.filewriter import write_file_meta_info
from pydicom.uid import ImplicitVRLittleEndian

from pynetdicom import AE, evt, debug_logger


# debug_logger()


TEST_DS_DIR = os.path.join(os.path.dirname(__file__), "dicom_files")


def init_yappi():
    """Initialise the profiler."""
    timestamp = datetime.now()
    timestamp = timestamp.strftime("%Y%m%d%H%M%S")
    OUT_FILE = "{}.profile".format(timestamp)

    import atexit
    import yappi

    print("[YAPPI START]")
    yappi.set_clock_type("wall")
    yappi.start()

    @atexit.register
    def finish_yappi():
        yappi.stop()

        print("[YAPPI WRITE]")

        stats = yappi.get_func_stats()

        # 'ystat' is Yappi internal format
        for stat_type in ["pstat", "callgrind"]:
            print("writing {}.{}".format(OUT_FILE, stat_type))
            stats.save("{}.{}".format(OUT_FILE, stat_type), type=stat_type)

        print("\n[YAPPI FUNC_STATS]")

        print("writing {}.func_stats".format(OUT_FILE))
        with open("{}.func_stats".format(OUT_FILE), "w") as fh:
            stats.print_all(out=fh)

        print("\n[YAPPI THREAD_STATS]")

        print("writing {}.thread_stats".format(OUT_FILE))
        tstats = yappi.get_thread_stats()
        with open("{}.thread_stats".format(OUT_FILE), "w") as fh:
            tstats.print_all(out=fh)

        print("[YAPPI DONE]")


def which(program):
    # Determine if a given program is installed on PATH
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath and is_exe(program):
        return program

    # for path in os.environ["PATH"].split(os.pathsep):
    for path in sorted(os.environ["PATH"].split(os.pathsep), reverse=True):
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
    args = [which("storescp"), "--ignore", "11112"]
    return subprocess.Popen(args)


def start_pynetdicom_storescp():
    args = ["python", "-m", "pynetdicom", "storescp", "11112", "--ignore"]
    return subprocess.Popen(args)


def start_storescu(test_ds, ds_per_assoc):
    """Run DCMTK's storescu in a background process.

    Parameters
    ----------
    test_ds : pydicom.dataset.Dataset
        The test dataset to use
    ds_per_assoc : int
        The number of datasets to send using `storescu`.
    """
    fpath = test_ds.filename
    args = [which("storescu"), "localhost", "11112", "--repeat", f"{ds_per_assoc}", fpath]
    return subprocess.Popen(args)


def receive_store(test_ds, nr_assoc, ds_per_assoc, write_ds=0, use_yappi=False):
    """Run a Storage SCP and transfer datasets with sequential storescu's.

    Parameters
    ----------
    test_ds : pydicom.dataset.Dataset
        The test dataset to use
    nr_assoc : int
        The total number of (sequential) associations that will be made.
    ds_per_assoc : int
        The number of C-STORE requests sent per successful association.
    write_ds : int, optional
        ``0`` to not write to file (default),
        ``1`` to write the received dataset to file using event.dataset,
        ``2`` to write using the raw ``bytes``, .
        ``3`` to write raw bytes with unlimited PDU size.
    use_yappi : bool, optional
        True to use the yappi profiler, False otherwise (default).
    """
    if use_yappi:
        init_yappi()

    def handle(event):
        if write_ds == 1:
            with tempfile.TemporaryFile("w+b") as tfile:
                ds = event.dataset
                ds.file_meta = event.file_meta
                ds.save_as(tfile)
        elif write_ds in (2, 3):
            with tempfile.TemporaryFile("w+b") as tfile:
                tfile.write(b"\x00" * 128)
                tfile.write(b"DICM")
                write_file_meta_info(tfile, event.file_meta)
                tfile.write(event.request.DataSet.getvalue())

        return 0x0000

    ae = AE()
    ae.acse_timeout = 5
    ae.dimse_timeout = 5
    ae.network_timeout = 5
    if write_ds == 3:
        ae.maximum_pdu_size = 0
    ae.add_supported_context(test_ds.SOPClassUID, ImplicitVRLittleEndian)

    server = ae.start_server(
        ("localhost", 11112), block=False, evt_handlers=[(evt.EVT_C_STORE, handle)]
    )

    time.sleep(0.5)
    start_time = time.time()
    is_successful = True

    for ii in range(nr_assoc):
        p = start_storescu(test_ds, ds_per_assoc)
        # Block until transfer is complete
        p.wait()
        if p.returncode != 0:
            is_successful = False
            break

    if is_successful:
        write_msg = ["", " (write)", " (write fast)", " (write fastest)"][write_ds]
        print(
            f"C-STORE SCP transferred {nr_assoc * ds_per_assoc} total "
            f"{os.path.basename(test_ds.filename)} datasets over "
            f"{nr_assoc} association{'' if nr_assoc == 1 else 's'}{write_msg} "
            f"in {time.time() - start_time:.2f} s"
        )
    else:
        print("C-STORE SCP benchmark failed")

    server.shutdown()


def receive_store_internal(
    test_ds, nr_assoc, ds_per_assoc, write_ds=0, use_yappi=False
):
    """Run a Storage SCP and transfer datasets with pynetdicom alone.

    Parameters
    ----------
    test_ds : pydicom.dataset.Dataset
        The test dataset to use
    nr_assoc : int
        The total number of (sequential) associations that will be made.
    ds_per_assoc : int
        The number of C-STORE requests sent per successful association.
    write_ds : int, optional
        ``0`` to not write to file (default),
        ``1`` to write the received dataset to file using event.dataset,
        ``2`` to write using the raw ``bytes``, .
        ``3`` to write raw bytes with unlimited PDU size.
    use_yappi : bool, optional
        True to use the yappi profiler, False otherwise (default).
    """
    if use_yappi:
        init_yappi()

    server = start_pynetdicom_storescp()

    ae = AE()
    ae.acse_timeout = 5
    ae.dimse_timeout = 5
    ae.network_timeout = 5
    ae.add_requested_context(test_ds.SOPClassUID, ImplicitVRLittleEndian)

    time.sleep(0.5)
    start_time = time.time()
    is_successful = True

    for ii in range(nr_assoc):
        assoc = ae.associate("127.0.0.1", 11112)
        if assoc.is_established:
            for jj in range(ds_per_assoc):
                assoc.send_c_store(test_ds)

            assoc.release()

    if is_successful:
        print(
            f"C-STORE SCU/SCP transferred {nr_assoc * ds_per_assoc} total "
            f"{os.path.basename(test_ds.filename)} datasets over "
            f"{nr_assoc} association{'' if nr_assoc == 1 else 's'} "
            f"in {time.time() - start_time:.2f} s"
        )
    else:
        print("C-STORE SCU/SCP benchmark failed")

    server.terminate()


def receive_store_dcmtk(test_ds, nr_assoc, ds_per_assoc, use_yappi=False):
    """Run a Storage SCP and transfer datasets with sequential storescu's.

    Parameters
    ----------
    test_ds : pydicom.dataset.Dataset
        The test dataset to use
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

    start_time = time.time()
    is_successful = True

    for ii in range(nr_assoc):
        p = start_storescu(test_ds, ds_per_assoc)
        # Block until transfer is complete
        p.wait()
        if p.returncode != 0:
            is_successful = False
            break

    if is_successful:
        print(
            f"C-STORE DCMTK SCU/SCP transferred {nr_assoc * ds_per_assoc} total "
            f"{os.path.basename(test_ds.filename)} datasets over "
            f"{nr_assoc} association{'' if nr_assoc == 1 else 's'} "
            f"in {time.time() - start_time:.2f} s"
        )
    else:
        print("C-STORE DCMTK SCU/SCP benchmark failed")

    server.terminate()
    time.sleep(0.5)


def receive_store_simultaneous(test_ds, nr_assoc, ds_per_assoc, use_yappi=False):
    """Run a Storage SCP and transfer datasets with simultaneous storescu's.

    Parameters
    ----------
    test_ds : pydicom.dataset.Dataset
        The test dataset to use
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
    ae.add_supported_context(test_ds.SOPClassUID, ImplicitVRLittleEndian)

    server = ae.start_server(
        ("localhost", 11112), block=False, evt_handlers=[(evt.EVT_C_STORE, handle)]
    )

    time.sleep(0.5)
    start_time = time.time()
    is_successful = True

    processes = []
    for ii in range(nr_assoc):
        processes.append(start_storescu(test_ds, ds_per_assoc))

    while None in [pp.poll() for pp in processes]:
        pass

    returncodes = list(set([pp.returncode for pp in processes]))
    if len(returncodes) != 1 or returncodes[0] != 0:
        is_successful = False

    if is_successful:
        print(
            f"C-STORE SCP transferred {nr_assoc * ds_per_assoc} total "
            f"{os.path.basename(test_ds.filename)} datasets over "
            f"{nr_assoc} association{'' if nr_assoc == 1 else 's'} "
            f"in {time.time() - start_time:.2f} s"
        )
    else:
        print("C-STORE SCP benchmark failed")

    server.shutdown()


def send_store(test_ds, nr_assoc, ds_per_assoc, use_yappi=False):
    """Send a number of sequential C-STORE requests.

    Parameters
    ----------
    test_ds : pydicom.dataset.Dataset
        The test dataset to use
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
    ae.add_requested_context(test_ds.SOPClassUID, ImplicitVRLittleEndian)

    # Start timer
    start_time = time.time()
    run_times = []

    is_successful = True

    for ii in range(nr_assoc):
        if not is_successful:
            break

        assoc = ae.associate("localhost", 11112)

        if assoc.is_established:
            for jj in range(ds_per_assoc):
                try:
                    status = assoc.send_c_store(test_ds)
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

    end_time = time.time()
    if is_successful:
        print(
            f"C-STORE SCU transferred {nr_assoc * ds_per_assoc} total "
            f"{os.path.basename(test_ds.filename)} datasets over "
            f"{nr_assoc} association{'' if nr_assoc == 1 else 's'} "
            f"in {end_time - start_time:.2f} s"
        )
    else:
        print("C-STORE SCU benchmark failed")

    server.terminate()
    time.sleep(0.5)


if __name__ == "__main__":
    print("Use yappi? (y/n): ", end="")
    use_yappi = input()
    if use_yappi in ["y", "Y"]:
        use_yappi = True
    else:
        use_yappi = False

    print("Use large dataset? (y/n): ", end="")
    use_large_dcm = input()
    if use_large_dcm in ["y", "Y"]:
        use_large_dcm = True
    else:
        use_large_dcm = False

    if use_large_dcm:
        ds_name = "RTImageStorage.dcm"  # 2.1 MB
        default_nr_ds = 100
    else:
        ds_name = "CTImageStorage.dcm"  # 39 kB
        default_nr_ds = 1000

    print(f"number of datasets? (default = {default_nr_ds}): ", end="")
    try:
        nr_ds = int(input())
    except ValueError:
        nr_ds = default_nr_ds

    test_ds = dcmread(os.path.join(TEST_DS_DIR, ds_name))

    print(f"Which benchmarks do you wish to run? (list, range, or all)")
    print(f"  1. Storage SCU, {nr_ds} {ds_name} datasets over 1 association")
    print(
        f"  2. Storage SCU, 1 {ds_name} dataset per association over {nr_ds} associations"
    )
    print(f"  3. Storage SCP, {nr_ds} {ds_name} datasets over 1 association")
    print(f"  4. Storage SCP, {nr_ds} {ds_name} datasets over 1 association (write)")
    print(
        f"  5. Storage SCP, {nr_ds} {ds_name} datasets over 1 association (write fast)"
    )
    print(
        f"  6. Storage SCP, {nr_ds} {ds_name} datasets over 1 association (write fastest)"
    )
    print(
        f"  7. Storage SCP, 1 {ds_name} dataset per association over {nr_ds} associations"
    )
    print(
        f"  8. Storage SCP, {nr_ds} {ds_name} datasets per association over 10 simultaneous associations"
    )
    print(f"  9. Storage SCU/SCP, {nr_ds} {ds_name} datasets over 1 association")
    print(f"  10. Storage DCMTK SCU/SCP, {nr_ds} {ds_name} datasets over 1 association")

    bench_input = input()
    if re.fullmatch(r"\s*(a|all)\s*", bench_input):
        # All: "a" or "all"
        bench_list = [str(i) for i in range(1, 11)]
    elif re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", bench_input):
        # Range: "x - y"
        match = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", bench_input)
        bench_list = [
            str(i) for i in range(int(match.group(1)), int(match.group(2)) + 1)
        ]
    else:
        # List: "a, b, c"
        bench_list = re.findall(r"\d+", bench_input)

    if "1" in bench_list:
        send_store(test_ds, 1, nr_ds, use_yappi)
    if "2" in bench_list:
        send_store(test_ds, nr_ds, 1, use_yappi)
    if "3" in bench_list:
        receive_store(test_ds, 1, nr_ds, 0, use_yappi)
    if "4" in bench_list:
        receive_store(test_ds, 1, nr_ds, 1, use_yappi)
    if "5" in bench_list:
        receive_store(test_ds, 1, nr_ds, 2, use_yappi)
    if "6" in bench_list:
        receive_store(test_ds, 1, nr_ds, 3, use_yappi)
    if "7" in bench_list:
        receive_store(test_ds, nr_ds, 1, 0, use_yappi)
    if "8" in bench_list:
        receive_store_simultaneous(test_ds, 10, nr_ds, use_yappi)
    if "9" in bench_list:
        receive_store_internal(test_ds, 1, nr_ds, 0, use_yappi)
    if "10" in bench_list:
        receive_store_dcmtk(test_ds, 1, nr_ds, use_yappi)
