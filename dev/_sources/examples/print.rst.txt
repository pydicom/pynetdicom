Print Management Service Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The DICOM :dcm:`Print Management service<part04/chapter_H.html>`
facilitates print of images and image related data. There are two Basic Print
Management Meta SOP Classes which correspond with the minimum functionality
that an implementation of the Print Management service class shall support (i.e
at a minimum one of the two Meta SOP Classes must be supported):

* *Basic Grayscale Print Management Meta SOP Class* which is defined by support
  of

  * *Basic Film Session SOP Class*
  * *Basic Film Box SOP Class*
  * *Basic Greyscale Image Box SOP Class*
  * *Printer SOP Class*.
* *Basic Color Print Management Meta SOP Class* which is defined by support
  of

  * *Basic Film Session SOP Class*
  * *Basic Film Box SOP Class*
  * *Basic Color Image Box SOP Class*
  * *Printer SOP Class*.

Which utilise the following SOP Classes:

* *Basic Film Session SOP Class*, used with N-CREATE, N-SET, N-DELETE and
  N-ACTION to describe the presentation parameters that are common for all
  the films of a film session (e.g. all films to be printed)
* *Basic Film Box SOP Class* used with N-CREATE, N-ACTION, N-DELETE and N-SET
  to describe the presentation parameters that are common for all images
  on a given sheet of film (e.g. for a single film).
* *Basic Greyscale Image Box SOP Class* used with N-SET to describe the
  presentation of an image and image related data in the image area of a film.
* *Basic Colour Image Box SOP Class* used with N-SET to describe the
  presentation of an image and image related data in the image area of a film.
* *Printer SOP Class* used with N-EVENT-REPORT and N-GET to monitor the status
  of the printer.

There are also the following SOP Classes that are not included under
the Meta Print Management SOP Classes and which may optionally be supported:

* *Basic Annotation Box SOP Class* used with N-SET to describe the presentation
  of an annotation on a film.
* *Print Job SOP Class* used with N-EVENT-REPORT and N-GET to monitor the
  execution of the print process. Receiving N-EVENT-REPORT requests from the
  SCP when acting as an SCU is not supported and any such requests will
  automatically be responded to with a ``0x0000`` - Success status.
* *Printer Configuration Retrieval SOP Class* used with N-GET to retrieve key
  imaging characteristics of the printer.
* *Presentation LUT SOP Class* used with N-CREATE and N-DELETE to prepare image
  pixel data for display on devices that conform to the Grayscale Standard
  Display Function defined in Part 14 of the DICOM Standard.

Grayscale Print SCU
^^^^^^^^^^^^^^^^^^^

Overview
........

Over a single association:

1. Send an N-GET request to check the status of the printer.
2. Send an N-CREATE request to create a *Basic Film Session SOP Class*
   Instance.
3. Send an N-CREATE request to create a *Basic Film Box SOP Class* Instance
   within the *Film Session*. The SCP will also create one or more of the
   appropriate *Image Box SOP Class* Instances (*Basic Grayscale* or *Basic
   Color*) depending on the Meta SOP Class used to create the *Film Session*.
4. For each of the *Image Box SOP Class* Instances use N-SET to update its
   attributes with the image data and image attributes that are to be printed.
5. Use N-ACTION to command the *Film Box* to be printed or N-DELETE to delete
   the *Film Box*.
6. Repeat steps 1-5 as required.
7. Terminate the association to delete the *Film Session* hierarchy.

A Print SCP may send N-EVENT-REPORT service requests to the Print SCU (under
the Printer SOP Class) using one of the following methods,
depending on the implementation (check the conformance statement):

1. Over the same association as the Print SCU service request
2. Over a new association initiated by the Print SCP, which requires the SCP be
   configured with the details of the SCU
3. The next time the SCU associates with the SCP

Depending on which method the Print SCP uses you should:

* For methods 1 and 2, simply bind a handler to ``evt.EVT_N_REPORT``
  when calling
  :meth:`AE.associate()<pynetdicom.ae.ApplicationEntity.associate>`
* For method 3, start an :class:`~pynetdicom.transport.AssociationServer`
  instance with
  ``AE.start_server((addr, port), block=False)`` with a handler bound to
  ``evt.EVT_N_EVENT_REPORT``

To support minimal conformance for a Print SCU you can just use the handler
to return a status of ``0x0000`` and get the printer's current status manually
by sending an N-GET request.


DIMSE Services Available
........................

+-----------------+-------------------------+
| DIMSE-N Service | Usage SCU/SCP           |
+=================+=========================+
| *Basic Film Session SOP Class*            |
+-----------------+-------------------------+
| N-CREATE        | Mandatory/Mandatory     |
+-----------------+-------------------------+
| N-SET           | Optional/Mandatory      |
+-----------------+-------------------------+
| N-DELETE        | Optional/Mandatory      |
+-----------------+-------------------------+
| N-ACTION        | Optional/Optional       |
+-----------------+-------------------------+
| *Basic Film Box SOP Class*                |
+-----------------+-------------------------+
| N-CREATE        | Mandatory/Mandatory     |
+-----------------+-------------------------+
| N-ACTION        | Mandatory/Mandatory     |
+-----------------+-------------------------+
| N-DELETE        | Optional/Mandatory      |
+-----------------+-------------------------+
| N-SET           | Optional/Optional       |
+-----------------+-------------------------+
| *Basic Grayscale Image Box SOP Class*     |
+-----------------+-------------------------+
| N-SET           | Mandatory/Mandatory     |
+-----------------+-------------------------+
| *Printer SOP Class*                       |
+-----------------+-------------------------+
| N-EVENT-REPORT  | Mandatory/Mandatory     |
+-----------------+-------------------------+
| N-GET           | Optional/Mandatory      |
+-----------------+-------------------------+

Example
.......

Print the image data from a SOP Instance onto a single A4 page. For a real-life
Print SCP you would need to check its conformance statement to see what
print options (medium types, page sizes, layouts, etc) are supported. This
example assumes that the Film Session's and Film Box's
N-CREATE responses include conformant *Basic Film Session SOP Class* and
*Basic Film Box SOP Class* instances (which may not always be the case).

We also assume that the Print SCP sends the Printer SOP Class' N-EVENT-REPORT
notifications over the same association (and ignore them).

.. code-block:: python

    import sys

    from pydicom import dcmread
    from pydicom.dataset import Dataset
    from pydicom.uid import generate_uid

    from pynetdicom import AE, evt, debug_logger
    from pynetdicom.sop_class import (
        BasicGrayscalePrintManagementMeta,
        BasicFilmSession,
        BasicFilmBox,
        BasicGrayscaleImageBox,
        Printer,
        PrinterInstance
    )

    debug_logger()

    # The SOP Instance containing the grayscale image data to be printed
    DATASET = dcmread('path/to/file.dcm')


    def build_session():
        """Return an N-CREATE *Attribute List* for creating a Basic Film Session

        Returns
        -------
        pydicom.dataset.Dataset
            An N-CREATE *Attribute List* dataset that can be used to create a
            *Basic Film Session SOP Class* instance.
        """
        attr_list = Dataset()
        attr_list.NumberOfCopies = '1'  # IS
        attr_list.PrintPriority = 'LOW'  # CS
        attr_list.MediumType = 'PAPER'  # CS
        attr_list.FilmDestination = 'SOMEWHERE'  # CS
        attr_list.FilmSessionLabel = 'TEST JOB'  # LO
        attr_list.MemoryAllocation = ''  # IS
        attr_list.OwnerID = 'PYNETDICOM'  # SH

        return attr_list


    def build_film_box(session):
        """Return an N-CREATE *Attribute List* for creating a Basic Film Box.

        In this example we just have a single Image Box.

        Parameters
        ----------
        session : pydicom.dataset.Dataset
            The *Basic Film Session SOP Class* instance returned by SCP in
            response to the N-CREATE request that created it.

        Returns
        -------
        pydicom.dataset.Dataset
            An N-CREATE *Attribute List* dataset that can be used to create a
            *Basic Film Box SOP Class* instance.
        """
        # The "film" consists of a single Image Box
        attr_list = Dataset()
        attr_list.ImageDisplayFormat = 'STANDARD\1,1'
        attr_list.FilmOrientation = 'PORTRAIT'
        attr_list.FilmSizeID = 'A4'

        # Can only contain a single item, is a reference to the *Film Session*
        attr_list.ReferencedFilmSessionSequence = [Dataset()]
        item = attr_list.ReferencedFilmSessionSequence[0]
        item.ReferencedSOPClassUID = session.SOPClassUID
        item.ReferencedSOPInstanceUID = session.SOPInstanceUID

        return attr_list


    def build_image_box(im):
        """Return an N-SET *Attribute List* for updating a Basic Grayscale Image Box

        Parameters
        ----------
        im : pydicom.dataset.Dataset
            The SOP Instance containing the pixel data that is to be printed.

        Returns
        -------
        pydicom.dataset.Dataset
            An N-SET *Attribute List* dataset that can be used to update the
            *Basic Grayscale Image Box SOP Class* instance.
        """
        attr_list = Dataset()
        attr_list.ImageBoxPosition = 1  # US

        # Zero or one item only
        attr_list.ReferencedImageBoxSequence = [Dataset()]
        item = attr_list.ReferencedImageBoxSequence[0]
        item.SamplesPerPixel = im.SamplesPerPixel
        item.PhotometricInterpretation = im.PhotometricInterpretation
        item.Rows = im.Rows
        item.Columns = im.Columns
        item.BitsAllocated = im.BitsAllocated
        item.BitsStored = im.BitsStored
        item.HighBit = im.HighBit
        item.PixelRepresentation = im.PixelRepresentation
        item.PixelData = im.PixelData

        return attr_list

    def handle_n_er(event):
        """Ignore the N-EVENT-REPORT notification"""
        return 0x0000

    handlers = [(evt.EVT_N_EVENT_REPORT, handle_n_er)]

    ae = AE()
    ae.add_requested_context(BasicGrayscalePrintManagementMeta)
    assoc = ae.associate("127.0.0.1", 11112, evt_handlers=handlers)

    if assoc.is_established:
        # Step 1: Check the status of the printer
        # (2110,0010) Printer Status
        # (2110,0020) Printer Status Info
        # Because the association was negotiated using a presentation context
        #   with a Meta SOP Class we need to use the `meta_uid` keyword
        #   parameter to ensure we use the correct context
        status, attr_list = assoc.send_n_get(
            [0x21100010, 0x21100020],  # Attribute Identifier List
            Printer,  # Affected SOP Class UID
            PrinterInstance,  # Well-known Printer SOP Instance
            meta_uid=BasicGrayscalePrintManagementMeta
        )
        if status and status.Status == 0x0000:
            if getattr(attr_list, 'PrinterStatus', None) != "NORMAL":
                print("Printer status is not 'NORMAL'")
                assoc.release()
                sys.exit()
            else:
                print("Failed to get the printer status")
                assoc.release()
                sys.exit()
        else:
            print("Failed to get the printer status")
            assoc.release()
            sys.exit()

        print('Printer ready')

        # Step 2: Create *Film Session* instance
        status, film_session = assoc.send_n_create(
            build_session(),  # Attribute List
            BasicFilmSession,  # Affected SOP Class UID
            generate_uid(),  # Affected SOP Instance UID
            meta_uid=BasicGrayscalePrintManagementMeta
        )

        if not status or status.Status != 0x0000:
            print('Creation of Film Session failed, releasing association')
            assoc.release()
            sys.exit()

        print('Film Session created')

        # Step 3: Create *Film Box* and *Image Box(es)*
        status, film_box = assoc.send_n_create(
            build_film_box(film_session),
            BasicFilmBox,
            generate_uid(),
            meta_uid=BasicGrayscalePrintManagementMeta
        )
        if not status or status.Status != 0x0000:
            print('Creation of the Film Box failed, releasing association')
            assoc.release()
            sys.exit()

        print('Film Box created')

        # Step 4: Update the *Image Box* with the image data
        # In this example we only have one *Image Box* per *Film Box*
        # Get the Image Box's SOP Class and SOP Instance UIDs
        item = film_box.ReferencedImageBoxSequence[0]
        status, image_box = assoc.send_n_set(
            build_image_box(DATASET),
            item.ReferencedSOPClassUID,
            item.ReferencedSOPInstanceUID,
            meta_uid=BasicGrayscalePrintManagementMeta
        )
        if not status or status.Status != 0x0000:
            print('Updating the Image Box failed, releasing association')
            assoc.release()
            sys.exit()

        print('Updated the Image Box with the image data')

        # Step 5: Print the *Film Box*
        status, action_reply = assoc.send_n_action(
            None,  # No *Action Information* needed
            1,  # Print the Film Box
            film_box.SOPClassUID,
            film_box.SOPInstanceUID,
            meta_uid=BasicGrayscalePrintManagementMeta
        )
        if not status or status.Status != 0x0000:
            print('Printing the Film Box failed, releasing association')
            assoc.release()
            sys.exit()

        # The actual printing may occur after association release/abort
        print('Print command sent successfully')

        # Optional - Delete the Film Box
        status = assoc.send_n_delete(
            film_box.SOPClassUID,
            film_box.SOPInstanceUID
        )

        # Release the association
        assoc.release()
