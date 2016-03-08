#!/usr/bin/env python

import logging
import unittest

from pydicom.uid import UID, ImplicitVRLittleEndian

from pynetdicom.ae import AE, Association, ACSE, DIMSE
from pynetdicom.ul import DUL
from pynetdicom.uid import VerificationSOPClass

logger = logging.getLogger('pynetdicom')
handler = logging.StreamHandler()
logger.setLevel(logging.ERROR)

"""
ApplicationEntity(
                  ae_title='PYNETDICOM',
                  port=0, 
                  scu_sop_class=[], 
                  scp_sop_class=[],
                  transfer_syntax=[ExplicitVRLittleEndian,
                                   ImplicitVRLittleEndian,
                                   ExplicitVRBigEndian]
                 )
"""
class AEGoodTimeoutSetters(unittest.TestCase):
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
        
    def test_acse_timeout(self):
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


class AEGoodMiscSetters(unittest.TestCase):
    def test_ae_title_good(self):
        """ Check AE title change produces good value """
        ae = AE(scu_sop_class=['1.2.840.10008.1.1'])
        ae.ae_title = '     TEST     '
        self.assertTrue(ae.ae_title == 'TEST')
        ae.ae_title = '            TEST'
        self.assertTrue(ae.ae_title == 'TEST')
        ae.ae_title = '                 TEST'
        self.assertTrue(ae.ae_title == 'TEST')
        ae.ae_title = 'a            TEST'
        self.assertTrue(ae.ae_title == 'a            TES')
    
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


class AEGoodInitialisation(unittest.TestCase):
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


class AEBadInitialisation(unittest.TestCase):
    def test_ae_title_all_spaces(self):
        """ AE should fail if ae_title is all spaces """
        self.assertRaises(ValueError, AE, '                ', 0, [VerificationSOPClass])

    def test_ae_title_empty_str(self):
        """ AE should fail if ae_title is an empty str """
        self.assertRaises(ValueError, AE, '', 0, [VerificationSOPClass])

    def test_ae_title_not_string(self):
        """ AE should fail if ae_title is not a str """
        self.assertRaises(ValueError, AE, 55, 0, [VerificationSOPClass])
        pass

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


if __name__ == "__main__":
    unittest.main()
