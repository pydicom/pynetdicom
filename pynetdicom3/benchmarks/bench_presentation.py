"""Performance tests for the presentation module."""

from pydicom._uid_dict import UID_dictionary
from pydicom.uid import UID

from pynetdicom3 import StorageSOPClassList
from pynetdicom3.presentation import PresentationContext, PresentationService
from pynetdicom3.utils import PresentationContextManager


class TimePresentationContext:
    def setup(self):
        self.contexts = []
        for x in range(500):
            self.contexts.append(
                PresentationContext(1,
                                    '1.2.840.10008.5.1.4.1.1.2',
                                    ['1.2.840.10008.1.2',
                                     '1.2.840.10008.1.2.1',
                                     '1.2.840.10008.1.2.2'])
            )

    def time_create_single_transfer_syntax(self):
        """Time the creation of 100 presentation contexts with a single ts"""
        for x in range(500):
            PresentationContext(
                1,
                '1.2.840.10008.5.1.4.1.1.2',
                ['1.2.840.10008.1.2']
            )

    def time_create_double_transfer_syntax(self):
        for x in range(500):
            PresentationContext(
                1,
                '1.2.840.10008.5.1.4.1.1.2',
                ['1.2.840.10008.1.2', '1.2.840.10008.1.2.1']
            )

    def time_create_triple_transfer_syntax(self):
        for x in range(500):
            PresentationContext(
                1,
                '1.2.840.10008.5.1.4.1.1.2',
                [
                    '1.2.840.10008.1.2',
                    '1.2.840.10008.1.2.1',
                    '1.2.840.10008.1.2.2'
                ]
            )

    def time_create_from_sop(self):
        """Test the time taken to create a PresentationContext from every
        available standard DICOM UID.
        """
        for uid in UID_dictionary:
            PresentationContext(
                1,
                uid,
                [
                    '1.2.840.10008.1.2',
                    '1.2.840.10008.1.2.1',
                    '1.2.840.10008.1.2.2'
                ]
            )

    def time_create_from_sop_list(self):
        """Test the time taken to create Presentation Contexts using the
        predefined SOP Classes from the pyndx.sop_class module.
        """
        for ii, sop_class in enumerate(StorageSOPClassList):
            PresentationContext(
                ii * 2 + 1,
                sop_class.UID,
                [
                    '1.2.840.10008.1.2',
                    '1.2.840.10008.1.2.1',
                    '1.2.840.10008.1.2.2'
                ]
            )


class TimePresentationAcceptorRoleNegotiation(object):
    """Time presentation context negotiation as acceptor with SCP/SCU Role
    Selection
    """
    def setup(self):
        # Requestor presentation contexts - max 126
        self.requestor_contexts = []
        self.requestor_transfer_syntaxes = ['1.2.840.10008.1.2',
                                            '1.2.840.10008.1.2.1',
                                            '1.2.840.10008.1.2.2']
        for ii, sop in enumerate(StorageSOPClassList):
            context = PresentationContext(ii * 2 + 1,
                                          sop.UID,
                                          ['1.2.840.10008.1.2',
                                           '1.2.840.10008.1.2.1',
                                           '1.2.840.10008.1.2.2'])
            context.SCP = True
            context.SCU = True
            self.requestor_contexts.append(context)

        # Acceptor presentation contexts - no max
        self.acceptor_contexts = []
        self.acceptor_transfer_syntaxes = ['1.2.840.10008.1.2',
                                           '1.2.840.10008.1.2.1',
                                           '1.2.840.10008.1.2.2']
        for uid in UID_dictionary:
            context = PresentationContext(1,
                                uid,
                                ['1.2.840.10008.1.2',
                                 '1.2.840.10008.1.2.1',
                                 '1.2.840.10008.1.2.2'])
            context.SCP = True
            context.SCU = False
            self.acceptor_contexts.append(context)

    def time_ps_ac_role(self):
        """Time a presentation service with SCP/SCU role negotiation."""
        presentation = PresentationService()
        presentation.negotiate_as_requestor(self.requestor_contexts,
                                            self.acceptor_contexts)


    def time_pcm_ac_role(self):
        """Time PresentationContextManager with SCP/SCU role negotiation."""
        pcm = PresentationContextManager()
        pcm.requestor_contexts = self.requestor_contexts
        pcm.acceptor_contexts = self.acceptor_contexts


class TimePresentationRequestorRoleNegotiation(object):
    """Time presentation context negotiation as requestor with SCP/SCU Role
    Selection
    """
    def setup(self):
        # Requestor presentation contexts - max 126
        self.requestor_contexts = []
        self.requestor_transfer_syntaxes = ['1.2.840.10008.1.2',
                                            '1.2.840.10008.1.2.1',
                                            '1.2.840.10008.1.2.2']
        for ii, sop in enumerate(StorageSOPClassList):
            context = PresentationContext(ii * 2 + 1,
                                sop.UID,
                                ['1.2.840.10008.1.2',
                                 '1.2.840.10008.1.2.1',
                                 '1.2.840.10008.1.2.2'])
            context.SCP = True
            context.SCU = True
            self.requestor_contexts.append(context)

        # Acceptor presentation contexts - no max
        self.acceptor_contexts = []
        self.acceptor_transfer_syntaxes = ['1.2.840.10008.1.2',
                                           '1.2.840.10008.1.2.1',
                                           '1.2.840.10008.1.2.2']
        for uid in UID_dictionary:
            context = PresentationContext(1,
                                          uid,
                                          ['1.2.840.10008.1.2'])
            context.Result = 0x00
            context.SCP = True
            context.SCU = True
            self.acceptor_contexts.append(context)

    def time_ps_rq_role(self):
        """Time a presentation service with SCP/SCU role negotiation."""
        presentation = PresentationService()
        presentation.negotiate_as_requestor(self.requestor_contexts,
                                            self.acceptor_contexts)


    def time_pcm_rq_role(self):
        """Time PresentationContextManager with SCP/SCU role negotiation."""
        pcm = PresentationContextManager()
        pcm.requestor_contexts = self.requestor_contexts
        pcm.acceptor_contexts = self.acceptor_contexts


class TimePresentationAcceptor(object):
    """Time presentation context negotiation as acceptor"""
    def setup(self):
        # Requestor presentation contexts - max 126
        self.requestor_contexts = []
        self.requestor_transfer_syntaxes = ['1.2.840.10008.1.2',
                                            '1.2.840.10008.1.2.1',
                                            '1.2.840.10008.1.2.2']
        for ii, sop in enumerate(StorageSOPClassList):
            self.requestor_contexts.append(
                PresentationContext(ii * 2 + 1,
                                    sop.UID,
                                    ['1.2.840.10008.1.2',
                                     '1.2.840.10008.1.2.1',
                                     '1.2.840.10008.1.2.2'])
            )

        # Acceptor presentation contexts - no max
        self.acceptor_contexts = []
        self.acceptor_transfer_syntaxes = ['1.2.840.10008.1.2',
                                           '1.2.840.10008.1.2.1',
                                           '1.2.840.10008.1.2.2']
        for uid in UID_dictionary:
            self.acceptor_contexts.append(
                PresentationContext(1,
                                    uid,
                                    ['1.2.840.10008.1.2',
                                     '1.2.840.10008.1.2.1',
                                     '1.2.840.10008.1.2.2'])
            )

    def time_ps_ac_basic(self):
        """Time a basic presentation service negotiation"""
        presentation = PresentationService()

        presentation.negotiate_as_acceptor(self.requestor_contexts,
                                           self.acceptor_contexts)

    def time_pcm_basic(self):
        """Time a basic PresentationContextManager negotiation"""
        pcm = PresentationContextManager()
        pcm.requestor_contexts = self.requestor_contexts
        pcm.acceptor_contexts = self.acceptor_contexts
        accepted = pcm.accepted


class TimePresentationRequestor(object):
    """Time presentation context negotiation as requestor"""
    def setup(self):
        # Requestor presentation contexts - max 126
        self.requestor_contexts = []
        self.requestor_transfer_syntaxes = ['1.2.840.10008.1.2',
                                            '1.2.840.10008.1.2.1',
                                            '1.2.840.10008.1.2.2']
        for ii, sop in enumerate(StorageSOPClassList):
            self.requestor_contexts.append(
                PresentationContext(ii * 2 + 1,
                                    sop.UID,
                                    ['1.2.840.10008.1.2',
                                     '1.2.840.10008.1.2.1',
                                     '1.2.840.10008.1.2.2'])
            )

        # Acceptor presentation contexts - no max
        self.acceptor_contexts = []
        self.acceptor_transfer_syntaxes = ['1.2.840.10008.1.2',
                                           '1.2.840.10008.1.2.1',
                                           '1.2.840.10008.1.2.2']
        for uid in UID_dictionary:
            context = PresentationContext(1,
                                          uid,
                                          ['1.2.840.10008.1.2'])
            context.Result = 0x00
            self.acceptor_contexts.append(context)

    def time_ps_rq_basic(self):
        """Time a basic presentation service negotiation."""
        presentation = PresentationService()
        presentation.negotiate_as_requestor(self.requestor_contexts,
                                            self.acceptor_contexts)

    def time_pcm_rq_basic(self):
        """Time a basic PresentationContextManager negotiation"""
        pcm = PresentationContextManager()
        pcm.requestor_contexts = self.requestor_contexts
        pcm.acceptor_contexts = self.acceptor_contexts
