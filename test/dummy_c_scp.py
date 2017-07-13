"""Dummy DIMSE-C SCPs for use in unit tests"""

import logging
import os
import socket
import time
import threading

from pydicom import read_file
from pydicom.dataset import Dataset
from pydicom.uid import UID, ImplicitVRLittleEndian

from pynetdicom3 import AE, VerificationSOPClass
from pynetdicom3.sop_class import CTImageStorage, MRImageStorage, \
                                 RTImageStorage, \
                                 PatientRootQueryRetrieveInformationModelFind, \
                                 StudyRootQueryRetrieveInformationModelFind, \
                                 ModalityWorklistInformationFind, \
                                 PatientStudyOnlyQueryRetrieveInformationModelFind, \
                                 PatientRootQueryRetrieveInformationModelGet, \
                                 StudyRootQueryRetrieveInformationModelGet, \
                                 PatientStudyOnlyQueryRetrieveInformationModelGet, \
                                 PatientRootQueryRetrieveInformationModelMove, \
                                 StudyRootQueryRetrieveInformationModelMove, \
                                 PatientStudyOnlyQueryRetrieveInformationModelMove
from pynetdicom3.status import code_to_category


LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)

TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
BIG_DATASET = read_file(os.path.join(TEST_DS_DIR, 'RTImageStorage.dcm'))
DATASET = read_file(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm'))
COMP_DATASET = read_file(os.path.join(TEST_DS_DIR, 'MRImageStorage_JPG2000_Lossless.dcm'))


class DummyBaseSCP(threading.Thread):
    """Base class for the Dummy SCP classes"""
    bad_status = 0x0101
    def __init__(self):
        """Initialise the class"""
        self.ae.on_c_echo = self.on_c_echo
        self.ae.on_c_store = self.on_c_store
        self.ae.on_c_find = self.on_c_find
        self.ae.on_c_get = self.on_c_get
        self.ae.on_c_move = self.on_c_move
        threading.Thread.__init__(self)
        self.daemon = True

        self.delay = 0
        self.send_abort = False

    def run(self):
        """The thread run method"""
        self.ae.start()

    def stop(self):
        """Stop the SCP thread"""
        self.ae.stop()

    def abort(self):
        """Abort any associations"""
        for assoc in self.ae.active_associations:
            assoc.abort()

    def release(self):
        """Release any associations"""
        for assoc in self.ae.active_associations:
            assoc.release()

    def on_c_echo(self):
        """Callback for ae.on_c_echo"""
        raise RuntimeError("You should not have been able to get here.")

    def on_c_store(self, ds):
        """Callback for ae.on_c_store"""
        raise RuntimeError("You should not have been able to get here.")

    def on_c_find(self, ds):
        """Callback for ae.on_c_find"""
        raise RuntimeError("You should not have been able to get here.")

    def on_c_cancel_find(self):
        """Callback for ae.on_c_cancel_find"""
        raise RuntimeError("You should not have been able to get here.")

    def on_c_get(self, ds):
        """Callback for ae.on_c_get"""
        raise RuntimeError("You should not have been able to get here.")

    def on_c_cancel_get(self):
        """Callback for ae.on_c_cancel_get"""
        raise RuntimeError("You should not have been able to get here.")

    def on_c_move(self, ds, move_aet):
        """Callback for ae.on_c_move"""
        raise RuntimeError("You should not have been able to get here.")

    def on_c_cancel_move(self):
        """Callback for ae.on_c_cancel_move"""
        raise RuntimeError("You should not have been able to get here.")


class DummyVerificationSCP(DummyBaseSCP):
    """A threaded dummy verification SCP used for testing"""
    def __init__(self, port=11112):
        self.ae = AE(scp_sop_class=[VerificationSOPClass], port=port)
        DummyBaseSCP.__init__(self)
        self.status = 0x0000

    def on_c_echo(self):
        """Callback for ae.on_c_echo

        Parameters
        ----------
        delay : int or float
            Wait `delay` seconds before sending a response
        """
        time.sleep(self.delay)
        
        if self.send_abort:
            self.ae.active_associations[0].abort()

        return self.status


class DummyStorageSCP(DummyBaseSCP):
    """A threaded dummy storage SCP used for testing"""
    bad_status = 0xFFFF
    success = 0x0000

    def __init__(self, port=11112):
        self.ae = AE(scp_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                                    StudyRootQueryRetrieveInformationModelMove,
                                    PatientStudyOnlyQueryRetrieveInformationModelMove,
                                    CTImageStorage,
                                    RTImageStorage, MRImageStorage], port=port)
        DummyBaseSCP.__init__(self)
        self.status = self.success

    def on_c_store(self, ds):
        """Callback for ae.on_c_store"""
        time.sleep(self.delay)
        return self.status


class DummyFindSCP(DummyBaseSCP):
    """A threaded dummy find SCP used for testing"""
    success = 0x0000
    pending = 0xFF00
    bad_status = 0xFFFF
    matching_terminated_cancel = 0xFE00
    out_of_resources = 0xA700
    def __init__(self, port=11112):
        self.ae = AE(scp_sop_class=[PatientRootQueryRetrieveInformationModelFind,
                                    StudyRootQueryRetrieveInformationModelFind,
                                    ModalityWorklistInformationFind,
                                    PatientStudyOnlyQueryRetrieveInformationModelFind],
                     port=port)
        DummyBaseSCP.__init__(self)
        self.status = self.pending
        self.cancel = False

    def on_c_find(self, ds):
        """Callback for ae.on_c_find"""
        time.sleep(self.delay)
        ds = Dataset()
        ds.PatientName = '*'
        ds.QueryRetrieveLevel = "PATIENT"

        if self.cancel:
            yield 0xFE00, None

        if isinstance(self.status, Dataset):
            if self.status.Status in [0xFF00, 0xFF01]:
                yield self.status, ds
            else:
                yield self.status, None
        elif isinstance(self.status, int):
            if self.status in [0xFF00, 0xFF01]:
                yield self.status, ds
            else:
                yield self.status, None
        else:
            yield 0xC000, None

    def on_c_cancel_find(self):
        """Callback for ae.on_c_cancel_find"""
        self.cancel = True


class DummyGetSCP(DummyBaseSCP):
    """A threaded dummy get SCP used for testing"""
    success = 0x0000
    pending = 0xFF00
    def __init__(self, port=11112):
        self.ae = AE(scp_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                                    StudyRootQueryRetrieveInformationModelGet,
                                    PatientStudyOnlyQueryRetrieveInformationModelGet,
                                    CTImageStorage],
                     scu_sop_class=[CTImageStorage],
                     port=port)
        DummyBaseSCP.__init__(self)
        self.status = self.success
        self.cancel = False

    def on_c_get(self, ds):
        """Callback for ae.on_c_get"""
        time.sleep(self.delay)
        ds = Dataset()
        ds.PatientName = '*'
        ds.QueryRetrieveLevel = "PATIENT"
        if code_to_category(self.status) not in ['Pending', 'Warning']:
            yield 1
            yield self.status, None

        if self.cancel:
            yield 1
            yield self.cancel, None

        yield 2
        for ii in range(2):
            yield self.status, DATASET

    def on_c_cancel_get(self):
        """Callback for ae.on_c_cancel_get"""
        self.cancel = True


class DummyMoveSCP(DummyBaseSCP):
    """A threaded dummy move SCP used for testing"""
    success = 0x0000
    pending = 0xFF00

    def __init__(self, port=11112):
        self.ae = AE(scp_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                                    StudyRootQueryRetrieveInformationModelMove,
                                    PatientStudyOnlyQueryRetrieveInformationModelMove,
                                    RTImageStorage, CTImageStorage],
                     scu_sop_class=[RTImageStorage,
                                    CTImageStorage],
                     port=port)
        DummyBaseSCP.__init__(self)
        self.status = self.pending
        self.cancel = False

    def on_c_move(self, ds, move_aet):
        """Callback for ae.on_c_find"""
        time.sleep(self.delay)
        ds = Dataset()
        ds.PatientName = '*'
        ds.QueryRetrieveLevel = "PATIENT"

        # Check move_aet first
        if move_aet != b'TESTMOVE        ':
            yield 1
            yield None, None

        if code_to_category(self.status) not in ['Pending', 'Warning']:
            yield 1
            yield 'localhost', 11113
            yield self.status, None

        if self.cancel:
            yield 1
            yield 'localhost', 11113
            yield self.cancel, None

        yield 2
        yield 'localhost', 11113
        for ii in range(2):
            yield self.status, DATASET

    def on_c_cancel_find(self):
        """Callback for ae.on_c_cancel_move"""
        self.cancel = True
