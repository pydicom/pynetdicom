
.. currentmodule:: pynetdicom.presentation

.. _user_presentation_role:

C-GET and SCP/SCU Role Selection
--------------------------------

The final wrinkle in presentation context negotiation is :dcm:`SCP/SCU Role
Selection <part07/sect_D.3.3.4.html>`,
which allows an association *requestor* to propose it's role (SCU, SCP, or
SCU and SCP) for each proposed abstract syntax. Role selection is used for
services such as the Query/Retrieve Service's C-GET requests, where the
association *acceptor* sends data back to the *requestor*.

To propose SCP/SCU Role Selection as a *requestor* you should include
:class:`SCP_SCU_RoleSelectionNegotiation
<pynetdicom.pdu_primitives.SCP_SCU_RoleSelectionNegotiation>`
items in the extended negotiation, either by creating them from scratch or
using the :func:`build_role` convenience function:

.. code-block:: python

    from pynetdicom import AE, build_role
    from pynetdicom.pdu_primitives import SCP_SCU_RoleSelectionNegotiation
    from pynetdicom.sop_class import CTImageStorage, MRImageStorage

    ae = AE()
    ae.add_requested_context(CTImageStorage)
    ae.add_requested_context(MRImageStorage)

    role_a = SCP_SCU_RoleSelectionNegotiation()
    role_a.sop_class_uid = CTImageStorage
    role_a.scu_role = True
    role_a.scp_role = True

    role_b = build_role(MRImageStorage, scp_role=True)

    assoc = ae.associate("127.0.0.1", 11112, ext_neg=[role_a, role_b])

When acting as the *requestor* you can set **either or both** of *scu_role* and
*scp_role*, with the non-specified role assumed to be ``False``.

To support SCP/SCU Role Selection as an *acceptor* you can use the *scu_role*
and *scp_role* keyword parameters in :meth:`AE.add_supported_context()
<pynetdicom.ae.ApplicationEntity.add_supported_context>`:

.. code-block:: python

    from pynetdicom import AE
    from pynetdicom.pdu_primitives import SCP_SCU_RoleSelectionNegotiation
    from pynetdicom.sop_class import CTImageStorage

    ae = AE()
    ae.add_supported_context(CTImageStorage, scu_role=True, scp_role=False)
    ae.start_server(("127.0.0.1", 11112))

When acting as the *acceptor* **both** *scu_role* and *scp_role* must be
specified. A value of ``True`` indicates that the *acceptor* will accept the
proposed role. *pynetdicom* uses the following table to decide the outcome
of role selection negotiation:

.. _role_selection_negotiation:

+---------------------+---------------------+--------------------------+----------+
| *Requestor*         | *Acceptor*          | Outcome                  | Notes    |
+----------+----------+----------+----------+-------------+------------+          |
| scu_role | scp_role | scu_role | scp_role | *Requestor* | *Acceptor* |          |
+==========+==========+==========+==========+=============+============+==========+
| N/A      | N/A      | N/A      | N/A      | SCU         | SCP        | Default  |
+----------+----------+----------+----------+-------------+------------+----------+
| True     | True     | False    | False    | N/A         | N/A        | Rejected |
|          |          |          +----------+-------------+------------+----------+
|          |          |          | True     | SCP         | SCU        |          |
|          |          +----------+----------+-------------+------------+----------+
|          |          | True     | False    | SCU         | SCP        | Default  |
|          |          |          +----------+-------------+------------+----------+
|          |          |          | True     | SCU/SCP     | SCU/SCP    |          |
+----------+----------+----------+----------+-------------+------------+----------+
| True     | False    | False    | False    | N/A         | N/A        | Rejected |
|          |          +----------+          +-------------+------------+----------+
|          |          | True     |          | SCU         | SCP        | Default  |
+----------+----------+----------+----------+-------------+------------+----------+
| False    | True     | False    | False    | N/A         | N/A        | Rejected |
|          |          |          +----------+-------------+------------+----------+
|          |          |          | True     | SCP         | SCU        |          |
+----------+----------+----------+----------+-------------+------------+----------+
| False    | False    | False    | False    | N/A         | N/A        | Rejected |
+----------+----------+----------+----------+-------------+------------+----------+

As can be seen there are four possible outcomes:

* *Requestor* is SCU, *acceptor* is SCP (default roles)
* *Requestor* is SCP, *acceptor* is SCU
* *Requestor* and *acceptor* are both SCU/SCP
* *Requestor* and *acceptor* are neither (context rejected)

.. warning::
   Role selection negotiation is not very well defined by the DICOM Standard,
   so different implementations may not give the same outcomes.
