#!/usr/bin/env python

import logging
import threading
import unittest
from unittest.mock import patch

from pydicom.uid import UID, ImplicitVRLittleEndian

from pynetdicom3 import AE
from pynetdicom3 import VerificationSOPClass, StorageSOPClassList, \
    QueryRetrieveSOPClassList

logger = logging.getLogger('pynetdicom')
handler = logging.StreamHandler()
logger.setLevel(logging.CRITICAL)

"""
    Initialisation
    --------------
    AE(
       ae_title='PYNETDICOM',
       port=0, 
       scu_sop_class=[], 
       scp_sop_class=[],
       transfer_syntax=[ExplicitVRLittleEndian,
                        ImplicitVRLittleEndian,
                        ExplicitVRBigEndian]
      )

    Functions
    ---------
    AE.start()
    AE.stop()
    AE.quit()
    AE.associate(addr, port)

    Attributes
    ----------
    acse_timeout - int
    active_associations - list of pynetdicom.association.Association
    address - str
    ae_title - str
    client_socket - socket.socket
    dimse_timeout - int
    network_timeout - int
    maximum_associations - int
    maximum_pdu_size - int
    port - int
    presentation_contexts_scu - List of pynetdicom.utils.PresentationContext
    presentation_contexts_scp - List of pynetdicom.utils.PresentationContext
    require_calling_aet - str
    require_called_aet - str
    scu_supported_sop - List of pydicom.uid.UID
    scp_supported_sop - List of pydicom.uid.UID
    transfer_syntaxes - List of pydicom.uid.UID
    
    Callbacks
    ---------
    on_c_echo()
    on_c_store(dataset)
    on_c_find(dataset)
    on_c_find_cancel()
    on_c_get(dataset)
    on_c_get_cancel()
    on_c_move(dataset)
    on_c_move_cancel()
    
    on_n_event_report()
    on_n_get()
    on_n_set()
    on_n_action()
    on_n_create()
    on_n_delete()

    on_receive_connection()
    on_make_connection()
    
    on_association_requested(primitive)
    on_association_accepted(primitive)
    on_association_rejected(primitive)
    on_association_released(primitive)
    on_association_aborted(primitive)
"""


class AEVerificationSCP(threading.Thread):
    def __init__(self):
        self.ae = AE(port=11112, scp_sop_class=[VerificationSOPClass])
        threading.Thread.__init__(self)
        self.daemon = True
        self.start()
        
    def run(self):
        self.ae.start()
        
    def stop(self):
        self.ae.stop()


class AEStorageSCP(threading.Thread):
    def __init__(self):
        self.ae = AE(port=11112, scp_sop_class=StorageSOPClassList)
        threading.Thread.__init__(self)
        self.daemon = True
        self.start()
        
    def run(self):
        self.ae.start()
        
    def stop(self):
        self.ae.stop()


class TestAEGoodCallbacks(unittest.TestCase):
    def test_on_c_echo_called(self):
        """ Check that SCP AE.on_c_echo() was called """
        scp = AEVerificationSCP()
        
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        with patch.object(scp.ae, 'on_c_echo') as mock:
            assoc.send_c_echo()
            
        mock.assert_called_with()
        
        assoc.release()
        
        self.assertRaises(SystemExit, scp.stop)
    
    def test_on_c_store_called(self):
        """ Check that SCP AE.on_c_store(dataset) was called """
        scp = AEStorageSCP()
        
        ae = AE(scu_sop_class=StorageSOPClassList)
        assoc = ae.associate('localhost', 11112)
        #with patch.object(scp.ae, 'on_c_store') as mock:
        #    assoc.send_c_store(dataset)
            
        #mock.assert_called_with()
        
        assoc.release()
        
        self.assertRaises(SystemExit, scp.stop)

    def test_on_c_find_called(self): pass
    def test_on_c_get_called(self): pass
    def test_on_c_move_called(self): pass
    def test_on_n_event_report_called(self): pass
    def test_on_n_get_called(self): pass
    def test_on_n_set_called(self): pass
    def test_on_n_action_called(self): pass
    def test_on_n_create_called(self): pass
    def test_on_n_delete_called(self): pass
    def test_on_receive_connection_called(self): pass
    def test_on_make_connection_called(self): pass
    def test_on_association_req_called(self): pass
    def test_on_association_acc_called(self): pass
    def test_on_association_rej_called(self): pass
    def test_on_association_rel_called(self): pass
    def test_on_association_abort_called(self): pass


class TestAEGoodAssociation(unittest.TestCase):
    def test_associate_establish_release(self):
        """ Check SCU Association with SCP """
        scp = AEVerificationSCP()
        
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established == True)
        
        assoc.release()
        self.assertTrue(assoc.is_established == False)
        
        self.assertRaises(SystemExit, scp.stop)
    
    def test_associate_max_pdu(self):
        """ Check Association has correct max PDUs on either end """
        scp = AEVerificationSCP()
        scp.ae.maximum_pdu_size = 54321
        
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112, max_pdu=12345)
        
        self.assertTrue(scp.ae.active_associations[0].local_max_pdu == 54321)
        self.assertTrue(scp.ae.active_associations[0].peer_max_pdu == 12345)
        self.assertTrue(assoc.local_max_pdu == 12345)
        self.assertTrue(assoc.peer_max_pdu == 54321)
        
        assoc.release()
        
        # Check 0 max pdu value
        assoc = ae.associate('localhost', 11112, max_pdu=0)
        self.assertTrue(assoc.local_max_pdu == 0)
        self.assertTrue(scp.ae.active_associations[0].peer_max_pdu == 0)
        
        assoc.release()
        self.assertRaises(SystemExit, scp.stop)
        
    def test_association_acse_timeout(self):
        """ Check that the Association timeouts are being set correctly """
        scp = AEVerificationSCP()
        scp.ae.acse_timeout = 0
        scp.ae.dimse_timeout = 0
        
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 0
        ae.dimse_timeout = 0
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(scp.ae.active_associations[0].acse_timeout == 0)
        self.assertTrue(scp.ae.active_associations[0].dimse_timeout == 0)
        self.assertTrue(assoc.acse_timeout == 0)
        self.assertTrue(assoc.dimse_timeout == 0)
        assoc.release()
        
        scp.ae.acse_timeout = 21
        scp.ae.dimse_timeout = 22
        ae.acse_timeout = 31
        ae.dimse_timeout = 32

        assoc = ae.associate('localhost', 11112)
        self.assertTrue(scp.ae.active_associations[0].acse_timeout == 21)
        self.assertTrue(scp.ae.active_associations[0].dimse_timeout == 22)
        self.assertTrue(assoc.acse_timeout == 31)
        self.assertTrue(assoc.dimse_timeout == 32)
        assoc.release()
        
        self.assertRaises(SystemExit, scp.stop)


class TestAEGoodTimeoutSetters(unittest.TestCase):
    def test_acse_timeout(self):
        """ Check AE ACSE timeout change produces good value """
        ae = AE(scu_sop_class=['1.2.840.10008.1.1'])
        ae.acse_timeout = None
        self.assertTrue(ae.acse_timeout == 0)
        ae.acse_timeout = -100
        self.assertTrue(ae.acse_timeout == 0)
        ae.acse_timeout = 'a'
        self.assertTrue(ae.acse_timeout == 0)
        ae.acse_timeout = 0
        self.assertTrue(ae.acse_timeout == 0)
        ae.acse_timeout = 30
        self.assertTrue(ae.acse_timeout == 30)
        
    def test_dimse_timeout(self):
        """ Check AE DIMSE timeout change produces good value """
        ae = AE(scu_sop_class=['1.2.840.10008.1.1'])
        ae.dimse_timeout = None
        self.assertTrue(ae.dimse_timeout == 0)
        ae.dimse_timeout = -100
        self.assertTrue(ae.dimse_timeout == 0)
        ae.dimse_timeout = 'a'
        self.assertTrue(ae.dimse_timeout == 0)
        ae.dimse_timeout = 0
        self.assertTrue(ae.dimse_timeout == 0)
        ae.dimse_timeout = 30
        self.assertTrue(ae.dimse_timeout == 30)
        
    def test_network_timeout(self):
        """ Check AE network timeout change produces good value """
        ae = AE(scu_sop_class=['1.2.840.10008.1.1'])
        ae.network_timeout = None
        self.assertTrue(ae.network_timeout == 60)
        ae.network_timeout = -100
        self.assertTrue(ae.network_timeout == 60)
        ae.network_timeout = 'a'
        self.assertTrue(ae.network_timeout == 60)
        ae.network_timeout = 0
        self.assertTrue(ae.network_timeout == 0)
        ae.network_timeout = 30
        self.assertTrue(ae.network_timeout == 30)


class TestAEGoodMiscSetters(unittest.TestCase):
    def test_ae_title_good(self):
        """ Check AE title change produces good value """
        ae = AE(scu_sop_class=['1.2.840.10008.1.1'])
        ae.ae_title = '     TEST     '
        self.assertTrue(ae.ae_title == 'TEST            ')
        ae.ae_title = '            TEST'
        self.assertTrue(ae.ae_title == 'TEST            ')
        ae.ae_title = '                 TEST'
        self.assertTrue(ae.ae_title == 'TEST            ')
        ae.ae_title = 'a            TEST'
        self.assertTrue(ae.ae_title == 'a            TES')
        ae.ae_title = 'a        TEST'
        self.assertTrue(ae.ae_title == 'a        TEST   ')
    
    def test_max_assoc_good(self):
        """ Check AE maximum association change produces good value """
        ae = AE(scu_sop_class=['1.2.840.10008.1.1'])
        ae.maximum_associations = -10
        self.assertTrue(ae.maximum_associations == 1)
        ae.maximum_associations = ['a']
        self.assertTrue(ae.maximum_associations == 1)
        ae.maximum_associations = '10'
        self.assertTrue(ae.maximum_associations == 1)
        ae.maximum_associations = 0
        self.assertTrue(ae.maximum_associations == 1)
        ae.maximum_associations = 5
        self.assertTrue(ae.maximum_associations == 5)
    
    def test_max_pdu_good(self):
        """ Check AE maximum pdu size change produces good value """
        ae = AE(scu_sop_class=['1.2.840.10008.1.1'])
        ae.maximum_pdu_size = -10
        self.assertTrue(ae.maximum_pdu_size == 16382)
        ae.maximum_pdu_size = ['a']
        self.assertTrue(ae.maximum_pdu_size == 16382)
        ae.maximum_pdu_size = '10'
        self.assertTrue(ae.maximum_pdu_size == 16382)
        ae.maximum_pdu_size = 0
        self.assertTrue(ae.maximum_pdu_size == 0)
        ae.maximum_pdu_size = 5000
        self.assertTrue(ae.maximum_pdu_size == 5000)
        
    def test_req_calling_aet(self):
        """ Check AE require calling aet change produces good value """
        ae = AE(scu_sop_class=['1.2.840.10008.1.1'])
        ae.require_calling_aet = -10
        self.assertTrue(ae.require_calling_aet == '')
        ae.require_calling_aet = ['a']
        self.assertTrue(ae.require_calling_aet == '')
        ae.require_calling_aet = '10'
        self.assertTrue(ae.require_calling_aet == '10')
        ae.require_calling_aet = '     TEST     '
        self.assertTrue(ae.require_calling_aet == 'TEST')
        ae.require_calling_aet = '            TEST'
        self.assertTrue(ae.require_calling_aet == 'TEST')
        ae.require_calling_aet = '                 TEST'
        self.assertTrue(ae.require_calling_aet == 'TEST')
        ae.require_calling_aet = 'a            TEST'
        self.assertTrue(ae.require_calling_aet == 'a            TES')
        
    def test_req_called_aet(self):
        """ Check AE require called aet change produces good value """
        ae = AE(scu_sop_class=['1.2.840.10008.1.1'])
        ae.require_called_aet = -10
        self.assertTrue(ae.require_called_aet == '')
        ae.require_called_aet = ['a']
        self.assertTrue(ae.require_called_aet == '')
        ae.require_called_aet = '10'
        self.assertTrue(ae.require_called_aet == '10')
        ae.require_called_aet = '     TEST     '
        self.assertTrue(ae.require_called_aet == 'TEST')
        ae.require_called_aet = '            TEST'
        self.assertTrue(ae.require_called_aet == 'TEST')
        ae.require_called_aet = '                 TEST'
        self.assertTrue(ae.require_called_aet == 'TEST')
        ae.require_called_aet = 'a            TEST'
        self.assertTrue(ae.require_called_aet == 'a            TES')


class TestAEGoodInitialisation(unittest.TestCase):
    def test_sop_classes_good_uid(self):
        """ Check AE initialisation produces valid supported SOP classes """
        ae = AE(scu_sop_class=['1.2.840.10008.1.1', '1.2.840.10008.1.1.1'])
        self.assertTrue(ae.scu_supported_sop == [UID('1.2.840.10008.1.1'), 
                                                 UID('1.2.840.10008.1.1.1')])
        ae = AE(scu_sop_class=[UID('1.2.840.10008.1.1')])
        self.assertTrue(ae.scu_supported_sop == [UID('1.2.840.10008.1.1')])
        ae = AE(scu_sop_class=[VerificationSOPClass])
        self.assertTrue(ae.scu_supported_sop == [UID('1.2.840.10008.1.1')])
        ae = AE(scu_sop_class=[1, VerificationSOPClass, 3])
        self.assertTrue(ae.scu_supported_sop == [UID('1.2.840.10008.1.1')])

        ae = AE(scp_sop_class=['1.2.840.10008.1.1', '1.2.840.10008.1.1.1'])
        self.assertTrue(ae.scp_supported_sop == [UID('1.2.840.10008.1.1'), 
                                                 UID('1.2.840.10008.1.1.1')])
        ae = AE(scp_sop_class=[UID('1.2.840.10008.1.1')])
        self.assertTrue(ae.scp_supported_sop == [UID('1.2.840.10008.1.1')])
        ae = AE(scp_sop_class=[VerificationSOPClass])
        self.assertTrue(ae.scp_supported_sop == [UID('1.2.840.10008.1.1')])
        ae = AE(scp_sop_class=[1, VerificationSOPClass, 3])
        self.assertTrue(ae.scp_supported_sop == [UID('1.2.840.10008.1.1')])
    
    def test_transfer_syntax_good_uid(self):
        """ Check AE initialisation produces valid transfer syntaxes """
        ae = AE(scu_sop_class=['1.2.840.10008.1.1'], 
                transfer_syntax=['1.2.840.10008.1.2'])
        self.assertTrue(ae.transfer_syntaxes == [UID('1.2.840.10008.1.2')])
        
        ae = AE(scu_sop_class=['1.2.840.10008.1.1'], 
                transfer_syntax=['1.2.840.10008.1.2', '1.2.840.10008.1.1'])
        self.assertTrue(ae.transfer_syntaxes == [UID('1.2.840.10008.1.2')])
        
        ae = AE(scu_sop_class=['1.2.840.10008.1.1'], 
                transfer_syntax=['1.2.840.10008.1.2', '1.2.840.10008.1.2.2'])
        self.assertTrue(ae.transfer_syntaxes == [UID('1.2.840.10008.1.2'),
                                                 UID('1.2.840.10008.1.2.2')])
        
        ae = AE(scu_sop_class=['1.2.840.10008.1.1'], 
                transfer_syntax=[UID('1.2.840.10008.1.2')])
        self.assertTrue(ae.transfer_syntaxes == [UID('1.2.840.10008.1.2')])
        
        ae = AE(scu_sop_class=['1.2.840.10008.1.1'], 
                transfer_syntax=[ImplicitVRLittleEndian])
        self.assertTrue(ae.transfer_syntaxes == [UID('1.2.840.10008.1.2')])


class TestAEBadInitialisation(unittest.TestCase):
    def test_ae_title_all_spaces(self):
        """ AE should fail if ae_title is all spaces """
        self.assertRaises(ValueError, AE, '                ', 0, [VerificationSOPClass])

    def test_ae_title_empty_str(self):
        """ AE should fail if ae_title is an empty str """
        self.assertRaises(ValueError, AE, '', 0, [VerificationSOPClass])

    def test_ae_title_not_string(self):
        """ AE should fail if ae_title is not a str """
        self.assertRaises(TypeError, AE, 55, 0, [VerificationSOPClass])

    def test_ae_title_invalid_chars(self):
        """ AE should fail if ae_title is not a str """
        self.assertRaises(ValueError, AE, 'TEST\ME', 0, [VerificationSOPClass])
        self.assertRaises(ValueError, AE, 'TEST\nME', 0, [VerificationSOPClass])
        self.assertRaises(ValueError, AE, 'TEST\rME', 0, [VerificationSOPClass])
        self.assertRaises(ValueError, AE, 'TEST\tME', 0, [VerificationSOPClass])

    def test_port_not_numeric(self):
        """ AE should fail if port is not numeric """
        self.assertRaises(TypeError, AE, 'TESTSCU', 'a', [VerificationSOPClass])

    def test_port_not_int(self):
        """ AE should fail if port is not a int """
        self.assertRaises(TypeError, AE, 'TESTSCU', 100.8, [VerificationSOPClass])

    def test_port_not_positive(self):
        """ AE should fail if port is not >= 0 """
        self.assertRaises(ValueError, AE, 'TESTSCU', -1, [VerificationSOPClass])

    def test_no_sop_classes(self):
        """ AE should fail if scu_sop_class and scp_sop_class are both empty lists """
        self.assertRaises(ValueError, AE)
        
    def test_sop_classes_not_list(self):
        """ AE should fail if scu_sop_class or scp_sop_class are not lists """
        self.assertRaises(ValueError, AE, 'TEST', 0, VerificationSOPClass, [])
        self.assertRaises(ValueError, AE, 'TEST', 0, [], VerificationSOPClass)
        
    def test_sop_classes_not_list_of_sop_class(self):
        """ AE should fail if scu_sop_class or scp_sop_class are not lists of SOP classes """
        self.assertRaises(ValueError, AE, 'TEST', 0, [1, 2, 'a'], [])
        self.assertRaises(ValueError, AE, 'TEST', 0, [], [1, 'a', 3])

    def test_sop_classes_bad_class(self):
        """ AE should fail if given bad sop classes """
        self.assertRaises(ValueError, AE, 'TEST', 0, ['1.2.840.10008.1.1.'], [])
        self.assertRaises(ValueError, AE, 'TEST', 0, ['1.2.840.10008.1.1', 1, 'abst'], [])
        self.assertRaises(ValueError, AE, 'TEST', 0, ['1.2.840.10008.1.1', '1.2.840.1.1.'], [])
        self.assertRaises(ValueError, AE, 'TEST', 0, [UID('1.2.840.10008.1.1.')], [])
        self.assertRaises(ValueError, AE, 'TEST', 0, [], ['1.2.840.10008.1.1.'])
        self.assertRaises(ValueError, AE, 'TEST', 0, [], ['1.2.840.10008.1.1', 1, 'abst'])
        self.assertRaises(ValueError, AE, 'TEST', 0, [], ['1.2.840.10008.1.1', '1.2.840.1.1.'])
        self.assertRaises(ValueError, AE, 'TEST', 0, [], [UID('1.2.840.10008.1.1.')])
        
    def test_no_transfer_syntax(self):
        """ AE should fail if empty transfer_syntax """
        self.assertRaises(ValueError, AE, 'TEST', 0, [VerificationSOPClass], [], [])
        
    def test_transfer_syntax_not_list(self):
        """ AE should fail if transfer_syntax is not a list """
        self.assertRaises(ValueError, AE, 'TEST', 0, [VerificationSOPClass], [], 123)
        
    def test_transfer_syntax_not_list_of_uid(self):
        """ AE should fail if transfer_syntax is not a list of UIDs"""
        self.assertRaises(ValueError, AE, 'TEST', 0, [VerificationSOPClass], [], [123])
    
    def test_transfer_syntax_not_list_of_valid_uid(self):
        """ AE should fail if transfer_syntax is not a list of valid transfer syntax UIDs"""
        self.assertRaises(ValueError, AE, 'TEST', 0, [VerificationSOPClass], [], ['1.2.840.1008.1.2', 
                                                                                   '1.2.840.10008.1.1.'])
    
    def test_transfer_syntax_not_list_of_transfer_uid(self):
        """ AE should fail if transfer_syntax is not a list of valid transfer syntax UIDs"""
        self.assertRaises(ValueError, AE, 'TEST', 0, [VerificationSOPClass], [], ['1.2.840.10008.1.1'])


class TestAE_GoodRelease(unittest.TestCase):
    def test_ae_release_assoc(self):
        """ Association releases OK """
        # Start Verification SCP
        scp = AEVerificationSCP()
        
        ae = AE(scu_sop_class=[VerificationSOPClass])
        
        # Test N associate/release cycles
        for ii in range(10):
            assoc = ae.associate('localhost', 11112)
            self.assertTrue(assoc.is_established)
            
            if assoc.is_established:
                assoc.release()
                self.assertTrue(assoc.is_established == False)
                self.assertTrue(assoc.is_released == True)
                self.assertTrue(ae.active_associations == [])
        
        # Kill Verification SCP (important!)
        self.assertRaises(SystemExit, scp.stop)


class TestAE_GoodAbort(unittest.TestCase):
    def test_ae_aborts_assoc(self):
        """ Association aborts OK """
        # Start Verification SCP
        scp = AEVerificationSCP()
        
        ae = AE(scu_sop_class=[VerificationSOPClass])
        
        # Test N associate/abort cycles
        for ii in range(10):
            assoc = ae.associate('localhost', 11112)
            self.assertTrue(assoc.is_established)
            
            if assoc.is_established:
                assoc.abort()
                self.assertTrue(assoc.is_established == False)
                self.assertTrue(assoc.is_aborted == True)
                self.assertTrue(assoc.is_released == False)
                self.assertTrue(ae.active_associations == [])
        
        # Kill Verification SCP (important!)
        self.assertRaises(SystemExit, scp.stop)


if __name__ == "__main__":
    unittest.main()
