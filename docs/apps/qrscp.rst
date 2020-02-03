=====
qrscp
=====
    ``qrscp.py [options] port``


Query Keys
==========

U - Unique keys, R - Required keys, O - Optional keys

*Query/Retrieve Level* PATIENT (or STUDY for Study Root Q/R models)

.. code-block:: text

   (0010,0010) Patient's Name
   (0010,0020) Patient ID

*Query/Retrieve Level* STUDY

.. code-block:: text

   (0008,0020) Study Date
   (0020,000D) Study Instance UID

*Query/Retrieve Level* SERIES

.. code-block:: text

   (0008,0060) Modality
   (0020,000E) Series Instance UID

*Query/Retrieve Level* IMAGE

.. code-block:: text

   (0020,0013) SOP Instance UID
