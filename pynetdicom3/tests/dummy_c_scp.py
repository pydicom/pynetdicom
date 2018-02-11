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
from pynetdicom3.sop_class import (
    CTImageStorage, MRImageStorage, RTImageStorage,
    PatientRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelFind,
    ModalityWorklistInformationFind,
    PatientStudyOnlyQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelGet,
    StudyRootQueryRetrieveInformationModelGet,
    PatientStudyOnlyQueryRetrieveInformationModelGet,
    PatientRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelMove,
    PatientStudyOnlyQueryRetrieveInformationModelMove
)
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
    def __init__(self, port=11112):
        self.ae = AE(scp_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                                    StudyRootQueryRetrieveInformationModelMove,
                                    PatientStudyOnlyQueryRetrieveInformationModelMove,
                                    CTImageStorage,
                                    RTImageStorage, MRImageStorage], port=port)
        DummyBaseSCP.__init__(self)
        self.status = 0x0000
        self.raise_exception = False

    def on_c_store(self, ds):
        """Callback for ae.on_c_store"""
        time.sleep(self.delay)
        if self.raise_exception:
            raise ValueError('Dummy msg')
        return self.status


class DummyFindSCP(DummyBaseSCP):
    """A threaded dummy find SCP used for testing"""
    def __init__(self, port=11112):
        self.ae = AE(scp_sop_class=[PatientRootQueryRetrieveInformationModelFind,
                                    StudyRootQueryRetrieveInformationModelFind,
                                    ModalityWorklistInformationFind,
                                    PatientStudyOnlyQueryRetrieveInformationModelFind],
                     port=port)
        DummyBaseSCP.__init__(self)
        self.statuses = [0x0000]
        identifier = Dataset()
        identifier.PatientName = 'Test'
        self.identifiers = [identifier]
        self.cancel = False

    def on_c_find(self, ds):
        """Callback for ae.on_c_find"""
        time.sleep(self.delay)

        for status, identifier in zip(self.statuses, self.identifiers):
            if self.cancel:
                yield 0xFE00, None
                return
            yield status, identifier

    def on_c_cancel_find(self):
        """Callback for ae.on_c_cancel_find"""
        self.cancel = True


class DummyGetSCP(DummyBaseSCP):
    """A threaded dummy get SCP used for testing"""
    def __init__(self, port=11112):
        self.ae = AE(scp_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                                    StudyRootQueryRetrieveInformationModelGet,
                                    PatientStudyOnlyQueryRetrieveInformationModelGet,
                                    CTImageStorage],
                     scu_sop_class=[CTImageStorage],
                     port=port)
        DummyBaseSCP.__init__(self)
        self.statuses = [0x0000]
        ds = Dataset()
        ds.PatientName = 'Test'
        ds.SOPClassUID = CTImageStorage.UID
        ds.SOPInstanceUID = '1.2.3.4'
        self.datasets = [ds]
        self.no_suboperations = 1
        self.cancel = False

    def on_c_get(self, ds):
        """Callback for ae.on_c_get"""
        time.sleep(self.delay)
        ds = Dataset()
        ds.PatientName = '*'
        ds.QueryRetrieveLevel = "PATIENT"

        yield self.no_suboperations
        for (status, ds) in zip(self.statuses, self.datasets):
            if self.cancel:
                yield 0xFE00, None
                return
            yield status, ds

    def on_c_cancel_get(self):
        """Callback for ae.on_c_cancel_get"""
        self.cancel = True


class DummyMoveSCP(DummyBaseSCP):
    """A threaded dummy move SCP used for testing"""
    def __init__(self, port=11112):
        self.ae = AE(scp_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                                    StudyRootQueryRetrieveInformationModelMove,
                                    PatientStudyOnlyQueryRetrieveInformationModelMove,
                                    RTImageStorage, CTImageStorage],
                     scu_sop_class=[RTImageStorage, CTImageStorage],
                     port=port)
        DummyBaseSCP.__init__(self)
        self.statuses = [0x0000]
        self.store_status = 0x0000
        ds = Dataset()
        ds.PatientName = 'Test'
        ds.SOPClassUID = CTImageStorage.UID
        ds.SOPInstanceUID = '1.2.3.4'
        self.datasets = [ds]
        self.no_suboperations = 1
        self.destination_ae = ('localhost', 11112)
        self.cancel = False
        self.test_no_yield = False
        self.test_no_subops = False

    def on_c_move(self, ds, move_aet):
        """Callback for ae.on_c_move"""
        time.sleep(self.delay)
        ds = Dataset()
        ds.PatientName = '*'
        ds.QueryRetrieveLevel = "PATIENT"

        if self.test_no_yield:
            return

        yield self.destination_ae

        if self.test_no_subops:
            return

        yield self.no_suboperations
        for (status, ds) in zip(self.statuses, self.datasets):
            if self.cancel:
                yield 0xFE00, None
                return
            yield status, ds

    def on_c_store(self, ds):
        return self.store_status

    def on_c_cancel_move(self):
        """Callback for ae.on_c_cancel_move"""
        self.cancel = True
