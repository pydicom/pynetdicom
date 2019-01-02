"""Performance tests for the presentation module."""

from copy import deepcopy

from pydicom._uid_dict import UID_dictionary
from pydicom.uid import UID

from pynetdicom import StoragePresentationContexts, build_context
from pynetdicom.presentation import (
    PresentationContext,
    negotiate_as_acceptor,
    negotiate_as_requestor
)


class TimePresentationContext:
    def setup(self):
        self.contexts = []
        for x in range(500):
            cx = PresentationContext()
            cx.context_id = 1
            cx.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
            cx.transfer_syntax = ['1.2.840.10008.1.2',
                                  '1.2.840.10008.1.2.1',
                                  '1.2.840.10008.1.2.2']
            self.contexts.append(cx)

    def time_create_single_transfer_syntax(self):
        """Time creating contexts with a single transfer syntax"""
        for x in range(500):
            cx = PresentationContext()
            cx.context_id = 1
            cx.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
            cx.transfer_syntax = ['1.2.840.10008.1.2']

    def time_create_double_transfer_syntax(self):
        """Time creating context with two transfer syntaxes."""
        for x in range(500):
            cx = PresentationContext()
            cx.context_id = 1
            cx.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
            cx.transfer_syntax = ['1.2.840.10008.1.2', '1.2.840.10008.1.2.1']

    def time_create_triple_transfer_syntax(self):
        """Time creating context with three transfer syntaxes."""
        for x in range(500):
            cx = PresentationContext()
            cx.context_id = 1
            cx.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
            cx.transfer_syntax = ['1.2.840.10008.1.2',
                                  '1.2.840.10008.1.2.1',
                                  '1.2.840.10008.1.2.2']

    def time_create_from_sop(self):
        """Test the time taken to create a PresentationContext from every
        available standard DICOM UID.
        """
        for uid in UID_dictionary:
            cx = PresentationContext()
            cx.context_id = 1
            cx.abstract_syntax = uid
            cx.transfer_syntax = ['1.2.840.10008.1.2',
                                  '1.2.840.10008.1.2.1',
                                  '1.2.840.10008.1.2.2']


class TimePresentationAcceptorRoleNegotiation(object):
    """Time presentation context negotiation as acceptor with SCP/SCU Role
    Selection
    """
    def setup(self):
        # Requestor presentation contexts - max 126
        self.requestor_contexts = []
        for ii, cx in enumerate(StoragePresentationContexts):
            cx.context_id = ii * 2 + 1
            cx.scp_role = True
            cx.scu_role = True
            self.requestor_contexts.append(cx)

        # Acceptor presentation contexts - no max
        self.acceptor_contexts = []
        for uid in UID_dictionary:
            cx = PresentationContext()
            cx.abstract_syntax = uid
            cx.transfer_syntax = ['1.2.840.10008.1.2',
                                  '1.2.840.10008.1.2.1',
                                  '1.2.840.10008.1.2.2']
            self.acceptor_contexts.append(cx)

        self.ac_roles = {uid : (True, False) for uid in UID_dictionary}

    def time_ps_ac_role(self):
        """Time a presentation service with SCP/SCU role negotiation."""
        for ii in range(100):
            negotiate_as_requestor(
                self.requestor_contexts,
                self.acceptor_contexts,
                self.ac_roles
            )


class TimePresentationRequestorRoleNegotiation(object):
    """Time presentation context negotiation as requestor with SCP/SCU Role
    Selection
    """
    def setup(self):
        # Requestor presentation contexts - max 126
        self.requestor_contexts = []
        for ii, cx in enumerate(StoragePresentationContexts):
            cx.context_id = ii * 2 + 1
            cx.SCP = True
            cx.SCU = True
            self.requestor_contexts.append(cx)

        # Acceptor presentation contexts - no max
        self.acceptor_contexts = []
        for uid in UID_dictionary:
            context = PresentationContext()
            context.context_id = 1
            context.abstract_syntax = uid
            context.transfer_syntax = ['1.2.840.10008.1.2']
            context.Result = 0x00
            context.SCP = True
            context.SCU = True
            self.acceptor_contexts.append(context)

    def time_ps_rq_role(self):
        """Time a presentation service with SCP/SCU role negotiation."""
        for ii in range(100):
            negotiate_as_requestor(
                self.requestor_contexts,
                self.acceptor_contexts
            )


class TimePresentationAcceptor(object):
    """Time presentation context negotiation as acceptor"""
    def setup(self):
        # Requestor presentation contexts - max 128
        self.requestor_contexts = []

        for ii, cx in enumerate(StoragePresentationContexts):
            cx.context_id = ii * 2 + 1
            self.requestor_contexts.append(cx)

        # Acceptor presentation contexts - no max
        self.acceptor_contexts = []

        for uid in UID_dictionary:
            cx = PresentationContext()
            cx.abstract_syntax = uid
            cx.transfer_syntax = ['1.2.840.10008.1.2',
                                  '1.2.840.10008.1.2.1',
                                  '1.2.840.10008.1.2.2']
            self.acceptor_contexts.append(cx)

    def time_ps_ac_basic(self):
        """Time a basic presentation service negotiation"""
        for ii in range(100):
            negotiate_as_acceptor(
                self.requestor_contexts,
                self.acceptor_contexts
            )


class TimePresentationRequestor(object):
    """Time presentation context negotiation as requestor"""
    def setup(self):
        # Requestor presentation contexts - max 126
        self.requestor_contexts = []
        for ii, cx in enumerate(StoragePresentationContexts):
            cx.context_id = ii * 2 + 1
            self.requestor_contexts.append(cx)

        # Acceptor presentation contexts - no max
        self.acceptor_contexts = []
        for ii, cx in enumerate(StoragePresentationContexts):
            cx = deepcopy(cx)
            cx.context_id = ii * 2 + 1
            cx.transfer_syntax = ['1.2.840.10008.1.2']
            cx.result = 0x00

            self.acceptor_contexts.append(cx)

    def time_ps_rq_basic(self):
        """Time a basic presentation service negotiation."""
        for ii in range(100):
            negotiate_as_requestor(
                self.requestor_contexts,
                self.acceptor_contexts
            )
