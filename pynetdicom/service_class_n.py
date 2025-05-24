"""Implements the supported Service Classes that make use of DIMSE-N."""

import logging
from typing import TYPE_CHECKING

from pynetdicom.dimse_primitives import (
    N_ACTION,
    N_CREATE,
    N_DELETE,
    N_EVENT_REPORT,
    N_GET,
    N_SET,
    C_FIND,
)
from pynetdicom.service_class import ServiceClass
from pynetdicom.status import (
    GENERAL_STATUS,
    APPLICATION_EVENT_LOGGING_SERVICE_CLASS_STATUS,
    MEDIA_CREATION_MANAGEMENT_SERVICE_CLASS_STATUS,
    PRINT_JOB_MANAGEMENT_SERVICE_CLASS_STATUS,
    PROCEDURE_STEP_STATUS,
    STORAGE_COMMITMENT_SERVICE_CLASS_STATUS,
    STORAGE_MANAGEMENT_SERVICE_CLASS_STATUS,
    RT_MACHINE_VERIFICATION_SERVICE_CLASS_STATUS,
    UNIFIED_PROCEDURE_STEP_SERVICE_CLASS_STATUS,
)

if TYPE_CHECKING:  # pragma: no cover
    from pynetdicom.presentation import PresentationContext

    _MCM = N_CREATE | N_GET | N_ACTION
    _PJ = N_CREATE | N_EVENT_REPORT | N_GET | N_SET | N_ACTION | N_DELETE
    _PS = N_CREATE | N_EVENT_REPORT | N_GET | N_SET
    _SCS = N_EVENT_REPORT | N_ACTION
    _SMS = N_ACTION | N_EVENT_REPORT
    _UPS = N_CREATE | N_EVENT_REPORT | N_GET | N_SET | N_ACTION | C_FIND


LOGGER = logging.getLogger(__name__)


class ApplicationEventLoggingServiceClass(ServiceClass):
    """Implementation of the Application Event Logging Service Class"""

    statuses = APPLICATION_EVENT_LOGGING_SERVICE_CLASS_STATUS

    def SCP(self, req: N_ACTION, context: "PresentationContext") -> None:
        """The SCP implementation for Application Event Logging Service Class.

        Parameters
        ----------
        req : dimse_primitives.N_ACTION
            The N-ACTION request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the service is operating under.
        """
        if isinstance(req, N_ACTION):
            self._n_action_scp(req, context)
        else:
            raise ValueError(
                f"Invalid DIMSE primitive '{req.__class__.__name__}' used "
                f"with Application Event Logging"
            )


class DisplaySystemManagementServiceClass(ServiceClass):
    """Implementation of the Display System Management Service Class."""

    statuses = GENERAL_STATUS

    def SCP(self, req: N_GET, context: "PresentationContext") -> None:
        """The SCP implementation for Display System Management.

        Parameters
        ----------
        req : dimse_primitives.N_GET
            The N-GET request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the service is operating under.
        """
        if isinstance(req, N_GET):
            self._n_get_scp(req, context)
        else:
            raise ValueError(
                f"Invalid DIMSE primitive '{req.__class__.__name__}' used "
                f"with Display System Management"
            )


class InstanceAvailabilityNotificationServiceClass(ServiceClass):
    """Implementation of the Instance Availability Service Class"""

    statuses = GENERAL_STATUS

    def SCP(self, req: N_CREATE, context: "PresentationContext") -> None:
        """The SCP implementation for Instance Availability Service Class.

        Parameters
        ----------
        req : dimse_primitives.N_CREATE
            The N-CREATE request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the service is operating under.
        """
        if isinstance(req, N_CREATE):
            self._n_create_scp(req, context)
        else:
            raise ValueError(
                f"Invalid DIMSE primitive '{req.__class__.__name__}' used "
                f"with Instance Availability"
            )


class MediaCreationManagementServiceClass(ServiceClass):
    """Implementation of the Media Creation Management Service Class"""

    statuses = MEDIA_CREATION_MANAGEMENT_SERVICE_CLASS_STATUS

    def SCP(self, req: "_MCM", context: "PresentationContext") -> None:
        """The SCP implementation for Media Creation Management Service Class.

        Parameters
        ----------
        req : dimse_primitives.N_CREATE or N_GET or N_ACTION
            The N-CREATE, N-GET or N-ACTION request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the service is operating under.
        """
        if isinstance(req, N_CREATE):
            self._n_create_scp(req, context)
        elif isinstance(req, N_GET):
            self._n_get_scp(req, context)
        elif isinstance(req, N_ACTION):
            self._n_action_scp(req, context)
        else:
            raise ValueError(
                f"Invalid DIMSE primitive '{req.__class__.__name__}' used "
                f"with Media Creation Management"
            )


class PrintManagementServiceClass(ServiceClass):
    """Implementation of the Print Management Service Class"""

    statuses = PRINT_JOB_MANAGEMENT_SERVICE_CLASS_STATUS

    def SCP(self, req: "_PJ", context: "PresentationContext") -> None:
        """The SCP implementation for Print Management Service Class.

        Parameters
        ----------
        req : dimse_primitives.N_CREATE or N_SET or N_DELETE or N_GET or N_EVENT_REPORT or N_ACTION
            The N-CREATE, N-SET, N-GET, N-DELETE, N-ACTION or N-EVENT-REPORT
            request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the service is operating under.
        """
        if isinstance(req, N_CREATE):
            self._n_create_scp(req, context)
        elif isinstance(req, N_EVENT_REPORT):
            self._n_event_report_scp(req, context)
        elif isinstance(req, N_GET):
            self._n_get_scp(req, context)
        elif isinstance(req, N_SET):
            self._n_set_scp(req, context)
        elif isinstance(req, N_ACTION):
            self._n_action_scp(req, context)
        elif isinstance(req, N_DELETE):
            self._n_delete_scp(req, context)
        else:
            raise ValueError(
                f"Invalid DIMSE primitive '{req.__class__.__name__}' used "
                f"with Print Management"
            )


class ProcedureStepServiceClass(ServiceClass):
    """Implementation of the Modality Performed Procedure Step Service Class"""

    statuses = PROCEDURE_STEP_STATUS

    def SCP(self, req: "_PS", context: "PresentationContext") -> None:
        """The SCP implementation for Modality Performed Procedure Step.

        Parameters
        ----------
        req : dimse_primitives.N_CREATE or N_SET or N_GET or N_EVENT_REPORT
            The N-CREATE, N-SET, N-GET or N-EVENT-REPORT request primitive
            sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the service is operating under.
        """
        if isinstance(req, N_CREATE):
            # Modality Performed Procedure Step
            self._n_create_scp(req, context)
        elif isinstance(req, N_EVENT_REPORT):
            # Modality Performed Procedure Step Notification
            self._n_event_report_scp(req, context)
        elif isinstance(req, N_GET):
            # Modality Performed Procedure Step Retrieve
            self._n_get_scp(req, context)
        elif isinstance(req, N_SET):
            # Modality Performed Procedure Step
            self._n_set_scp(req, context)
        else:
            raise ValueError(
                f"Invalid DIMSE primitive '{req.__class__.__name__}' used "
                f"with Modality Performed Procedure Step"
            )


class RTMachineVerificationServiceClass(ServiceClass):
    """Implementation of the RT Machine Verification Service Class"""

    statuses = RT_MACHINE_VERIFICATION_SERVICE_CLASS_STATUS

    def SCP(self, req: "_PJ", context: "PresentationContext") -> None:
        """The SCP implementation for RT Machine Verification Service Class.

        Parameters
        ----------
        req : dimse_primitives.N_CREATE or N_SET or N_DELETE or N_GET or N_EVENT_REPORT or N_ACTION
            The N-CREATE, N-SET, N-GET, N-DELETE, N-ACTION or N-EVENT-REPORT
            request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the service is operating under.
        """
        if isinstance(req, N_CREATE):
            self._n_create_scp(req, context)
        elif isinstance(req, N_EVENT_REPORT):
            self._n_event_report_scp(req, context)
        elif isinstance(req, N_GET):
            self._n_get_scp(req, context)
        elif isinstance(req, N_SET):
            self._n_set_scp(req, context)
        elif isinstance(req, N_ACTION):
            self._n_action_scp(req, context)
        elif isinstance(req, N_DELETE):
            self._n_delete_scp(req, context)
        else:
            raise ValueError(
                f"Invalid DIMSE primitive '{req.__class__.__name__}' used "
                f"with RT Machine Verification"
            )


class StorageCommitmentServiceClass(ServiceClass):
    """Implementation of the Storage Commitment Service Class"""

    statuses = STORAGE_COMMITMENT_SERVICE_CLASS_STATUS

    def SCP(self, req: "_SCS", context: "PresentationContext") -> None:
        """The SCP implementation for Storage Commitment Service Class.

        Parameters
        ----------
        req : dimse_primitives.N_EVENT_REPORT or N_ACTION
            The N-ACTION or N-EVENT-REPORT request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the service is operating under.
        """
        if isinstance(req, N_EVENT_REPORT):
            self._n_event_report_scp(req, context)
        elif isinstance(req, N_ACTION):
            self._n_action_scp(req, context)
        else:
            raise ValueError(
                f"Invalid DIMSE primitive '{req.__class__.__name__}' used "
                f"with Storage Commitment"
            )


class StorageManagementServiceClass(ServiceClass):
    """Implementation of the Storage Management Service Class

    .. versionadded:: 2.1
    """

    statuses = STORAGE_MANAGEMENT_SERVICE_CLASS_STATUS

    def SCP(self, req: "_SMS", context: "PresentationContext") -> None:
        """The SCP implementation for Storage Management Service Class.

        Parameters
        ----------
        req : dimse_primitives.N_EVENT_REPORT or N_ACTION
            The N-ACTION or N-EVENT-REPORT request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the service is operating under.
        """
        if isinstance(req, N_EVENT_REPORT):
            self._n_event_report_scp(req, context)
        elif isinstance(req, N_ACTION):
            self._n_action_scp(req, context)
        else:
            raise ValueError(
                f"Invalid DIMSE primitive '{req.__class__.__name__}' used "
                f"with Storage Management"
            )


class UnifiedProcedureStepServiceClass(ServiceClass):
    """Implementation of the Unified Procedure Step Service Class"""

    statuses = UNIFIED_PROCEDURE_STEP_SERVICE_CLASS_STATUS

    def SCP(self, req: "_UPS", context: "PresentationContext") -> None:
        """The SCP implementation for Unified Procedure Step Service Class.

        Parameters
        ----------
        req : dimse_primitives.N_CREATE or C_FIND or N_SET or N_GET or N_EVENT_REPORT or N_ACTION
            The N-CREATE, C-FIND, N-SET, N-GET, N-ACTION or N-EVENT-REPORT
            request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the service is operating under.
        """
        # UPS Push: N-CREATE, N-ACTION, N-GET
        # UPS Pull: C-FIND, N-GET, N-SET, N-ACTION
        # UPS Watch: N-ACTION, N-GET, C-FIND
        # UPS Event: N-EVENT-REPORT
        if isinstance(req, N_CREATE):
            self._n_create_scp(req, context)
        elif isinstance(req, N_EVENT_REPORT):
            self._n_event_report_scp(req, context)
        elif isinstance(req, N_GET):
            self._n_get_scp(req, context)
        elif isinstance(req, N_SET):
            self._n_set_scp(req, context)
        elif isinstance(req, N_ACTION):
            self._n_action_scp(req, context)
        elif isinstance(req, C_FIND):
            self._c_find_scp(req, context)
        else:
            raise ValueError(
                f"Invalid DIMSE primitive '{req.__class__.__name__}' used "
                f"with Unified Procedure Step"
            )
