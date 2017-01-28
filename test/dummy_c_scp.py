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
                                 PatientStudyOnlyQueryRetrieveInformationModelMove, \
                                 Status

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)


class DummyBaseSCP(threading.Thread):
    """Base class for the Dummy SCP classes"""
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
    def __init__(self):
        self.ae = AE(scp_sop_class=[VerificationSOPClass], port=11112)
        DummyBaseSCP.__init__(self)

    def on_c_echo(self):
        """Callback for ae.on_c_echo

        Parameters
        ----------
        delay : int or float
            Wait `delay` seconds before sending a response
        """
        time.sleep(self.delay)


class DummyStorageSCP(DummyBaseSCP):
    """A threaded dummy storage SCP used for testing"""
    out_of_resources = Status('Failure',
                              'Refused: Out of resources',
                              range(0xA700, 0xA7FF + 1))
    ds_doesnt_match_sop_fail = Status('Failure',
                                 'Error: Data Set does not match SOP Class',
                                 range(0xA900, 0xA9FF + 1))
    cant_understand = Status('Failure', 'Error: Cannot understand',
                             range(0xC000, 0xCFFF + 1))
    coercion_of_elements = Status('Warning', 'Coercion of Data Elements',
                                  range(0xB000, 0xB000 + 1))
    ds_doesnt_match_sop_warn = Status('Warning',
                                      'Data Set does not match SOP Class',
                                      range(0xB007, 0xB007 + 1))
    elem_discard = Status('Warning', 'Element Discarded',
                          range(0xB006, 0xB006 + 1))
    success = Status('Success', '', range(0x0000, 0x0000 + 1))

    def __init__(self):
        self.ae = AE(scp_sop_class=[CTImageStorage,
                                    RTImageStorage, MRImageStorage], port=11112)
        DummyBaseSCP.__init__(self)
        self.status = self.success

    def on_c_store(self, ds):
        """Callback for ae.on_c_store"""
        time.sleep(self.delay)
        return self.status


class DummyFindSCP(DummyBaseSCP):
    """A threaded dummy storage SCP used for testing"""
    out_of_resources = Status('Failure',
                            'Refused: Out of resources',
                            range(0xA700, 0xA700 + 1))
    identifier_doesnt_match_sop = Status('Failure',
                                            "Identifier does not match SOP "
                                            "Class",
                                            range(0xA900, 0xA900 + 1))
    unable_to_process = Status('Failure',
                             'Unable to process',
                             range(0xC000, 0xCFFF + 1))
    matching_terminated_cancel = Status('Cancel',
                                                  "Matching terminated due to "
                                                  "Cancel request",
                                                  range(0xFE00, 0xFE00 + 1))
    success = Status('Success',
                     'Matching is complete - No final Identifier is supplied',
                     range(0x0000, 0x0000 + 1))
    pending = Status('Pending',
                     "Matches are continuing - Current Match is supplied "
                     "and any Optional Keys were supported in the same manner "
                     "as 'Required Keys'",
                     range(0xFF00, 0xFF00 + 1))
    pending_warning = Status("Pending",
                            "Matches are continuing - Warning that one or more "
                            "Optional Keys were not supported for existence "
                            "and/or matching for this identifier",
                            range(0xFF01, 0xFF01 + 1))
    def __init__(self):
        self.ae = AE(scp_sop_class=[PatientRootQueryRetrieveInformationModelFind,
                                    StudyRootQueryRetrieveInformationModelFind,
                                    ModalityWorklistInformationFind,
                                    PatientStudyOnlyQueryRetrieveInformationModelFind],
                     port=11112)
        DummyBaseSCP.__init__(self)
        self.status = self.success

    def on_c_find(self, ds):
        """Callback for ae.on_c_find"""
        time.sleep(self.delay)
        ds = Dataset()
        ds.PatientName = '*'
        ds.QueryRetrieveLevel = "PATIENT"
        if self.status.status_type == 'Failure':
            yield self.status, None

        yield self.status, ds

    def on_c_cancel_find(self):
        """Callback for ae.on_c_cancel_find"""
        pass


class DummyGetSCP(DummyBaseSCP):
    """A threaded dummy storage SCP used for testing"""
    out_of_resources_no_matches = Status('Failure',
                                           'Refused: Out of resources - Unable '
                                           'to calcultate number of matches',
                                           range(0xA701, 0xA701 + 1))
    out_of_resources_unable = Status('Failure',
                                           'Refused: Out of resources - Unable '
                                           'to perform sub-operations',
                                           range(0xA702, 0xA702 + 1))
    identifier_doesnt_match_sop = Status('Failure',
                                            'Identifier does not match SOP '
                                            'Class',
                                            range(0xA900, 0xA900 + 1))
    unable = Status('Failure',
                             'Unable to process',
                             range(0xC000, 0xCFFF + 1))
    cancel = Status('Cancel',
                    'Sub-operations terminated due to Cancel indication',
                    range(0xFE00, 0xFE00 + 1))
    warning = Status('Warning',
                     'Sub-operations Complete - One or more Failures or '
                     'Warnings',
                     range(0xB000, 0xB000 + 1))
    success = Status('Success',
                     'Sub-operations Complete - No Failure or Warnings',
                     range(0x0000, 0x0000 + 1))
    pending = Status('Pending',
                     'Sub-operations are continuing',
                     range(0xFF00, 0xFF00 + 1))
    def __init__(self):
        self.ae = AE(scp_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                                    StudyRootQueryRetrieveInformationModelGet,
                                    PatientStudyOnlyQueryRetrieveInformationModelFind],
                     port=11112)
        DummyBaseSCP.__init__(self)
        self.status = self.success

    def on_c_get(self, ds):
        """Callback for ae.on_c_get"""
        time.sleep(self.delay)
        ds = Dataset()
        ds.PatientName = '*'
        ds.QueryRetrieveLevel = "PATIENT"

        #if self.status.status_type == 'Failure':
        #    yield self.status, None

        yield 0

    def on_c_cancel_get(self):
        """Callback for ae.on_c_cancel_get"""
        pass


class DummyMoveSCP(DummyBaseSCP):
    """A threaded dummy storage SCP used for testing"""
    out_of_resources_match = \
            Status('Failure',
                   'Refused: Out of resources - Unable to calcultate number ' \
                   'of matches',
                   range(0xA701, 0xA701 + 1))
    out_of_resources_unable = \
            Status('Failure',
                   'Refused: Out of resources - Unable to perform ' \
                   'sub-operations',
                   range(0xA702, 0xA702 + 1))
    move_destination_unknown = Status('Failure',
                                    'Refused: Move destination unknown',
                                    range(0xA801, 0xA801 + 1))
    identifier_doesnt_match_sop = \
            Status('Failure', 'Identifier does not match SOP Class',
                   range(0xA900, 0xA900 + 1))
    unable_to_process = Status('Failure', 'Unable to process',
                             range(0xC000, 0xCFFF + 1))
    cancel = Status('Cancel',
                    'Sub-operations terminated due to Cancel indication',
                    range(0xFE00, 0xFE00 + 1))
    warning = Status('Warning',
                     'Sub-operations Complete - One or more Failures or ' \
                     'Warnings',
                     range(0xB000, 0xB000 + 1))
    success = Status('Success',
                     'Sub-operations Complete - No Failure or Warnings',
                     range(0x0000, 0x0000 + 1))
    pending = Status('Pending', 'Sub-operations are continuing',
                     range(0xFF00, 0xFF00 + 1))
    def __init__(self):
        self.ae = AE(scp_sop_class=[PatientRootQueryRetrieveInformationModelMove],
                     port=11112)
        DummyBaseSCP.__init__(self)

    def on_c_move(self, ds):
        """Callback for ae.on_c_find"""
        time.sleep(self.delay)

    def on_c_cancel_find(self):
        """Callback for ae.on_c_cancel_move"""
        pass
