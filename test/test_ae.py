#!/usr/bin/env python

import logging
import signal
import threading
import time
import unittest
from unittest.mock import patch

from pydicom.uid import UID, ImplicitVRLittleEndian

from pynetdicom3 import AE
from pynetdicom3 import VerificationSOPClass, StorageSOPClassList, \
                        QueryRetrieveSOPClassList

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)


class AEVerificationSCP(threading.Thread):
    def __init__(self):
        self.ae = AE(port=11112, scp_sop_class=[VerificationSOPClass])
        threading.Thread.__init__(self)
        self.daemon = True

    def start_scp(self):
        self.start()

    def run(self):
        self.ae.start()

    def stop(self):
        self.ae.stop()

    def quit(self):
        self.ae.quit()


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


class TestAEVerificationSCU(unittest.TestCase):
    """
    TODO:
    * Check no matching transfer syntaxes
    * Check no matching abstract syntax
    """
    def setUp(self):
        self.ae = AEVerificationSCP()
        self.ae.start()

    def test_send_c_echo(self):
        """Test sending a c-echo"""
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', port=11112)
        if assoc.is_established:
            result = assoc.send_c_echo()
            self.assertEqual(result.status_type, 'Success')

        assoc.release()

        self.assertRaises(SystemExit, self.ae.stop)


class TestAEVerificationSCP(unittest.TestCase):
    """Check verification SCP"""
    def tearDown(self):
        for thread in threading.enumerate():
            if thread.name != 'MainThread':
                self.assertRaises(SystemExit, thread.stop)

    def test_bad_start(self):
        """Test bad startup"""
        ae = AE(scu_sop_class=[VerificationSOPClass])
        with self.assertRaises(ValueError):
            ae.start()

        self.assertRaises(SystemExit, ae.stop)

    def test_string_output(self):
        """Test string output"""
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.require_calling_aet = b'something'
        ae.require_called_aet = b'elsething'
        self.assertTrue('Explicit VR' in ae.__str__())
        self.assertTrue('Verification' in ae.__str__())
        self.assertTrue('0/2' in ae.__str__())
        self.assertTrue('something' in ae.__str__())
        self.assertTrue('elsething' in ae.__str__())
        ae.scp_supported_sop = StorageSOPClassList
        self.assertTrue('CT Image' in ae.__str__())

    def test_stop_scp_keyboard(self):
        """Test stopping the SCP with keyboard"""
        self.scp = AEVerificationSCP()
        self.scp.start()
        def test():
            raise KeyboardInterrupt

        self.assertRaises(KeyboardInterrupt, test)

    def test_stop_scp_quit(self):
        """Test stopping the SCP with quit"""
        self.scp = AEVerificationSCP()
        self.scp.start()
        self.assertRaises(SystemExit, self.scp.quit)


class TestAEGoodCallbacks(unittest.TestCase):
    def test_on_c_echo_called(self):
        """ Check that SCP AE.on_c_echo() was called """
        scp = AEVerificationSCP()
        scp.start()

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

    def test_on_user_identity_negotiation(self):
        """ Check that SCP AE.on_user_identity_negotiation() was called """
        #scp = AEVerificationSCP()
        #scp.start()
        #ae = AE(scu_sop_class=[VerificationSOPClass])
        #assoc = ae.associate('localhost', 11112)
        #with patch.object(scp.ae, 'on_user_identity_negotiation') as mock:
        #    assoc.send_c_echo()

        #mock.assert_called_with()
        #assoc.release()
        #self.assertRaises(SystemExit, scp.stop)
        pass


class TestAEGoodAssociation(unittest.TestCase):
    def test_associate_establish_release(self):
        """ Check SCU Association with SCP """
        scp = AEVerificationSCP()
        scp.start()

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
        scp.start()

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
        scp.start()

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


class TestAEBadAssociation(unittest.TestCase):
    def test_raise(self):
        """Test bad associate call"""
        scp = AEVerificationSCP()
        scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        with self.assertRaises(TypeError):
            ae.associate(1112, 11112)
        with self.assertRaises(TypeError):
            ae.associate('localhost', '1.2.3.4')

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
        # scu_sop_class
        ae = AE(scu_sop_class=['1.2.840.10008.1.1', '1.2.840.10008.1.1.1'])
        self.assertTrue(ae.scu_supported_sop == [UID('1.2.840.10008.1.1'),
                                                 UID('1.2.840.10008.1.1.1')])
        ae = AE(scu_sop_class=[UID('1.2.840.10008.1.1')])
        self.assertTrue(ae.scu_supported_sop == [UID('1.2.840.10008.1.1')])

        ae = AE(scu_sop_class=[VerificationSOPClass])
        self.assertTrue(ae.scu_supported_sop == [UID('1.2.840.10008.1.1')])

        ae = AE(scu_sop_class=[1, VerificationSOPClass, 3])
        self.assertTrue(ae.scu_supported_sop == [UID('1.2.840.10008.1.1')])

        # scp_sop_class
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

    def test_presentation_context_abstract(self):
        """Check the presentation context generation abstract syntax"""
        ## SCU SOP Classes
        # str -> UID
        ae = AE(scu_sop_class=['1.1'], transfer_syntax=['1.2.840.10008.1.2'])
        ab_syn = ae.presentation_contexts_scu[0].AbstractSyntax
        self.assertEqual(ab_syn, UID('1.1'))
        self.assertTrue(isinstance(ab_syn, UID))

        # UID no change
        ae = AE(scu_sop_class=[UID('1.2')], transfer_syntax=['1.2.840.10008.1.2'])
        ab_syn = ae.presentation_contexts_scu[0].AbstractSyntax
        self.assertEqual(ab_syn, UID('1.2'))
        self.assertTrue(isinstance(ab_syn, UID))

        # sop_class -> UID
        ae = AE(scu_sop_class=[VerificationSOPClass], transfer_syntax=['1.2.840.10008.1.2'])
        ab_syn = ae.presentation_contexts_scu[0].AbstractSyntax
        self.assertEqual(ab_syn, UID('1.2.840.10008.1.1'))
        self.assertTrue(isinstance(ab_syn, UID))

        # bytes -> UID
        ae = AE(scu_sop_class=[b'1.3'], transfer_syntax=['1.2.840.10008.1.2'])
        ab_syn = ae.presentation_contexts_scu[0].AbstractSyntax
        self.assertEqual(ab_syn, UID('1.3'))
        self.assertTrue(isinstance(ab_syn, UID))

        # If not str, bytes, UID, serviceclass raise
        with self.assertRaises(ValueError):
            ae = AE(scu_sop_class=[12345], transfer_syntax=['1.2.840.10008.1.2'])

        # If not valid UID raise
        with self.assertRaises(ValueError):
            ae = AE(scu_sop_class=['1.3.'], transfer_syntax=['1.2.840.10008.1.2'])

        ## SCP SOP Classes
        # str -> UID
        ae = AE(scp_sop_class=['1.1'], transfer_syntax=['1.2.840.10008.1.2'])
        ab_syn = ae.presentation_contexts_scp[0].AbstractSyntax
        self.assertEqual(ab_syn, UID('1.1'))
        self.assertTrue(isinstance(ab_syn, UID))

        # UID no change
        ae = AE(scp_sop_class=[UID('1.2')], transfer_syntax=['1.2.840.10008.1.2'])
        ab_syn = ae.presentation_contexts_scp[0].AbstractSyntax
        self.assertEqual(ab_syn, UID('1.2'))
        self.assertTrue(isinstance(ab_syn, UID))

        # sop_class -> UID
        ae = AE(scp_sop_class=[VerificationSOPClass], transfer_syntax=['1.2.840.10008.1.2'])
        ab_syn = ae.presentation_contexts_scp[0].AbstractSyntax
        self.assertEqual(ab_syn, UID('1.2.840.10008.1.1'))
        self.assertTrue(isinstance(ab_syn, UID))

        # bytes -> UID
        ae = AE(scp_sop_class=[b'1.3'], transfer_syntax=['1.2.840.10008.1.2'])
        ab_syn = ae.presentation_contexts_scp[0].AbstractSyntax
        self.assertEqual(ab_syn, UID('1.3'))
        self.assertTrue(isinstance(ab_syn, UID))

        # If not str, bytes, UID, serviceclass raise
        with self.assertRaises(ValueError):
            ae = AE(scp_sop_class=[12345], transfer_syntax=['1.2.840.10008.1.2'])

        # If not valid UID raise
        with self.assertRaises(ValueError):
            ae = AE(scp_sop_class=['1.3.'], transfer_syntax=['1.2.840.10008.1.2'])

    def test_presentation_context_transfer(self):
        """Check the presentation context generation transfer syntax"""
        # str -> UID
        ae = AE(scu_sop_class=['1.1'], transfer_syntax=['1.2.840.10008.1.2'])
        tran_syn = ae.presentation_contexts_scu[0].TransferSyntax[0]
        self.assertEqual(tran_syn, UID('1.2.840.10008.1.2'))
        self.assertTrue(isinstance(tran_syn, UID))

        # UID no change
        ae = AE(scu_sop_class=['1.2'], transfer_syntax=[b'1.2.840.10008.1.2'])
        tran_syn = ae.presentation_contexts_scu[0].TransferSyntax[0]
        self.assertEqual(tran_syn, UID('1.2.840.10008.1.2'))
        self.assertTrue(isinstance(tran_syn, UID))

        # bytes -> UID
        ae = AE(scu_sop_class=['1.3'], transfer_syntax=[UID('1.2.840.10008.1.2')])
        tran_syn = ae.presentation_contexts_scu[0].TransferSyntax[0]
        self.assertEqual(tran_syn, UID('1.2.840.10008.1.2'))
        self.assertTrue(isinstance(tran_syn, UID))

        # If not transfer syntax raise
        with self.assertRaises(ValueError):
            ae = AE(scu_sop_class=['1.3'], transfer_syntax=['1.2.840'])

        # If not str, bytes, UID raise
        with self.assertRaises(ValueError):
            ae = AE(scu_sop_class=['1.3'], transfer_syntax=[123456])

        # If not valid UID raise
        with self.assertRaises(ValueError):
            ae = AE(scu_sop_class=['1.3'], transfer_syntax=['1.2.3.4.5.'])

        # If no valid transfer syntax UID raise
        with self.assertRaises(ValueError):
            ae = AE(scu_sop_class=['1.3'], transfer_syntax=[])


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

    def test_sop_classes_too_many(self):
        """Presentation context list should be cutoff after 126 sop classes"""
        sop_classes = ['1.1'] * 130
        ae = AE(scu_sop_class=sop_classes, transfer_syntax=['1.2.840.10008.1.2'])
        self.assertEqual(len(ae.presentation_contexts_scu), 127)

    def test_sop_classes_bad_class(self):
        """ AE should fail if given bad sop classes """
        self.assertRaises(ValueError, AE, 'TEST', 0, ['1.2.840.10008.1.1.'], [])
        self.assertRaises(ValueError, AE, 'TEST', 0, ['1.2.840.10008.1.1.', 1, 'abst'], [])
        self.assertRaises(ValueError, AE, 'TEST', 0, [UID('1.2.840.10008.1.1.')], [])
        self.assertRaises(ValueError, AE, 'TEST', 0, [], ['1.2.840.10008.1.1.'])
        self.assertRaises(ValueError, AE, 'TEST', 0, [], ['1.2.840.10008.1.1.', 1, 'abst'])
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
        scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])

        # Test N associate/release cycles
        for ii in range(5):
            assoc = ae.associate('localhost', 11112)
            self.assertTrue(assoc.is_established)

            if assoc.is_established:
                assoc.release()
                self.assertFalse(assoc.is_established)
                self.assertFalse(assoc.is_aborted)
                self.assertTrue(assoc.is_released)
                self.assertFalse(assoc.is_rejected)
                #self.assertTrue(ae.active_associations == [])

        # Kill Verification SCP (important!)
        self.assertRaises(SystemExit, scp.stop)


class TestAE_GoodAbort(unittest.TestCase):
    def test_ae_aborts_assoc(self):
        """ Association aborts OK """
        # Start Verification SCP
        scp = AEVerificationSCP()
        scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])

        # Test N associate/abort cycles
        for ii in range(5):
            assoc = ae.associate('localhost', 11112)
            self.assertTrue(assoc.is_established)

            if assoc.is_established:
                assoc.abort()
                self.assertFalse(assoc.is_established)
                self.assertTrue(assoc.is_aborted)
                self.assertFalse(assoc.is_released)
                self.assertFalse(assoc.is_rejected)
                #self.assertTrue(ae.active_associations == [])

        # Kill Verification SCP (important!)
        self.assertRaises(SystemExit, scp.stop)


if __name__ == "__main__":
    unittest.main(warnings='ignore')
