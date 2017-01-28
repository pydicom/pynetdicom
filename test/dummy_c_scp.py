"""Dummy DIMSE-C SCPs for use in unit tests"""

import logging
import os
import socket
import time
import threading

from pydicom.uid import UID, ImplicitVRLittleEndian
from pydicom import read_file

from pynetdicom3 import AE, VerificationSOPClass
from pynetdicom3.SOPclass import CTImageStorage, MRImageStorage, \
                                 RTImageStorage, \
                                 PatientRootQueryRetrieveInformationModelFind, \
                                 PatientRootQueryRetrieveInformationModelGet, \
                                 PatientRootQueryRetrieveInformationModelMove, \
                                 Status

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.DEBUG)


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

    def on_c_get(self, ds):
        """Callback for ae.on_c_get"""
        raise RuntimeError("You should not have been able to get here.")

    def on_c_move(self, ds, move_aet):
        """Callback for ae.on_c_move"""
        raise RuntimeError("You should not have been able to get here.")


class DummyVerificationSCP(DummyBaseSCP):
    """A threaded dummy verification SCP used for testing"""
    def __init__(self):
        self.ae = AE(scp_sop_class=[VerificationSOPClass], port=11113)
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
                                    RTImageStorage, MRImageStorage], port=11113)
        DummyBaseSCP.__init__(self)
        self.status = self.success

    def on_c_store(self, ds):
        """Callback for ae.on_c_store"""
        time.sleep(self.delay)
        return self.status


class DummyFindSCP(DummyBaseSCP):
    """A threaded dummy storage SCP used for testing"""
    def __init__(self):
        self.ae = AE(scp_sop_class=[PatientRootQueryRetrieveInformationModelFind],
                     port=11113)
        DummyBaseSCP.__init__(self)

    def on_c_find(self, ds):
        """Callback for ae.on_c_find"""
        time.sleep(self.delay)


class DummyGetSCP(DummyBaseSCP):
    """A threaded dummy storage SCP used for testing"""
    def __init__(self):
        self.ae = AE(scp_sop_class=[PatientRootQueryRetrieveInformationModelGet],
                     port=11113)
        DummyBaseSCP.__init__(self)

    def on_c_get(self, ds):
        """Callback for ae.on_c_find"""
        time.sleep(self.delay)


class DummyMoveSCP(DummyBaseSCP):
    """A threaded dummy storage SCP used for testing"""
    def __init__(self):
        self.ae = AE(scp_sop_class=[PatientRootQueryRetrieveInformationModelMove],
                     port=11113)
        DummyBaseSCP.__init__(self)

    def on_c_move(self, ds):
        """Callback for ae.on_c_find"""
        time.sleep(self.delay)
