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
from pynetdicom3.status import Status
                                 

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.DEBUG)

TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
BIG_DATASET = read_file(os.path.join(TEST_DS_DIR, 'RTImageStorage.dcm'))
DATASET = read_file(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm'))
COMP_DATASET = read_file(os.path.join(TEST_DS_DIR, 'MRImageStorage_JPG2000_Lossless.dcm'))


class DummyBaseSCP(threading.Thread):
    """Base class for the Dummy SCP classes"""
    bad_status = Status(0x0101, 'Test', 'A test status')
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

    out_of_resources = Status(0xA700, 'Failure', 'Refused: Out of resources')
    ds_doesnt_match_sop_fail = Status(0xA900, 'Failure', 'Error: Data Set does not match SOP Class')
    cant_understand = Status(0xC000, 'Failure', 'Error: Cannot understand')
    coercion_of_elements = Status(0xB000, 'Warning', 'Coercion of Data Elements')
    ds_doesnt_match_sop_warn = Status(0xB007, 'Warning', 'Data Set does not match SOP Class')
    elem_discard = Status(0xB006, 'Warning', 'Element Discarded')
    success = Status(0x0000, 'Success', '')
    bad_status = Status(0xFFFF)

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
    out_of_resources = Status(0xA700, 'Failure','Refused: Out of resources')
    identifier_doesnt_match_sop = Status(0xA900, 'Failure',
                                            "Identifier does not match SOP Class")
    unable_to_process = Status(0xC000, 'Failure',
                             'Unable to process')
    matching_terminated_cancel = Status(0xFE00, 'Cancel',
                                                  "Matching terminated due to "
                                                  "Cancel request")
    success = Status(0x0000, 'Success',
                     'Matching is complete - No final Identifier is supplied')
    pending = Status(0xFF00, 'Pending',
                     "Matches are continuing - Current Match is supplied "
                     "and any Optional Keys were supported in the same manner "
                     "as 'Required Keys'")
    pending_warning = Status(0xFF01, "Pending",
                            "Matches are continuing - Warning that one or more "
                            "Optional Keys were not supported for existence "
                            "and/or matching for this identifier")
    bad_status = Status(0xFFFF)
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
        if not isinstance(self.status, Status):
            yield self.status, None
            return
        
        if self.status.category != 'Pending':
            yield self.status, None

        if self.cancel:
            yield self.matching_terminated_cancel, None

        yield self.status, ds

    def on_c_cancel_find(self):
        """Callback for ae.on_c_cancel_find"""
        self.cancel = True


class DummyGetSCP(DummyBaseSCP):
    """A threaded dummy get SCP used for testing"""
    out_of_resources_match = Status(0xA701, 'Failure',
                                           'Refused: Out of resources - Unable '
                                           'to calculate number of matches')
    out_of_resources_unable = Status(0xA702, 'Failure',
                                           'Refused: Out of resources - Unable '
                                           'to perform sub-operations')
    identifier_doesnt_match_sop = Status(0xA900, 'Failure',
                                            'Identifier does not match SOP '
                                            'Class')
    unable = Status(0xC000, 'Failure', 'Unable to process')
    cancel_status = Status(0xFE00, 'Cancel',
                    'Sub-operations terminated due to Cancel indication')
    warning = Status(0xB000, 'Warning',
                     'Sub-operations Complete - One or more Failures or '
                     'Warnings')
    success = Status(0x0000, 'Success',
                     'Sub-operations Complete - No Failure or Warnings')
    pending = Status(0xFF00, 'Pending', 'Sub-operations are continuing')
    
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
        if self.status.category not in ['Pending', 'Warning']:
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
    out_of_resources_match = \
            Status(0xA701, 'Failure',
                   'Refused: Out of resources - Unable to calculate number ' \
                   'of matches')
    out_of_resources_unable = \
            Status(0xA702, 'Failure',
                   'Refused: Out of resources - Unable to perform ' \
                   'sub-operations')
    move_destination_unknown = Status(0xA801, 'Failure',
                                    'Refused: Move destination unknown')
    identifier_doesnt_match_sop = \
            Status(0xA900, 'Failure', 'Identifier does not match SOP Class')
    unable_to_process = Status(0xC000, 'Failure', 'Unable to process')
    cancel_status = Status(0xFE00, 'Cancel',
                    'Sub-operations terminated due to Cancel indication')
    warning = Status(0xB000, 'Warning',
                     'Sub-operations Complete - One or more Failures or ' \
                     'Warnings')
    success = Status(0x0000, 'Success',
                     'Sub-operations Complete - No Failure or Warnings')
    pending = Status(0xFF00, 'Pending', 'Sub-operations are continuing')
    
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

        if self.status.category not in ['Pending', 'Warning']:
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
