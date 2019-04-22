Print Management Service Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The DICOM `Print Management service
<http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_H>`_
facilitates print of images and image related data. There are two Basic Print
Management Meta SOP Classes which correspond with the minimum functionality
that an implementation of the Print Management service class shall support (i.e
at a minimum either (or both) of the two Meta SOP Classes must be supported):

* *Basic Grayscale Print Management Meta SOP Class* which is defined by support
  of

  * *Basic Film Session SOP Class*
  * *Basic Film Box SOP Class*
  * *Basic Greyscale Image Box SOP Class* and
  * *Printer SOP Class*.
* *Basic Color Print Management Meta SOP Class* which is defined by support
  of

  * *Basic Film Session SOP Class*
  * *Basic Film Box SOP Class*
  * *Basic Color Image Box SOP Class* and
  * *Printer SOP Class*.

Which utilise the following SOP Classes:

* *Basic Film Session SOP Class*, used with N-CREATE, N-SET, N-DELETE and
  N-ACTION to describe the presentation parameters that are common for all
  the films of a film session (e.g. a number of films)
* *Basic Film Box SOP Class* used with N-CREATE, N-ACTION, N-DELETE and N-SET
  to describe the presentation parameters that are common for all images
  on a given sheet of film (e.g. for a single film).
* *Basic Greyscale Image Box SOP Class* used with N-SET to describe the
  presentation of an image and image related data in the image area of a film.
* *Basic Colour Image Box SOP Class* used with N-SET to describe the
  presentation of an image and image related data in the image area of a film.
* *Printer SOP Class* used with N-EVENT-REPORT and N-GET to monitor the status
  of the printer.

There are also the following *optional* SOP Classes which may be supported:

* *Basic Annotation Box SOP Class* used with N-SET to describe the presentation
  of an annotation on a film.
* *Print Job SOP Class* used with N-EVENT-REPORT and N-GET to monitor the
  execution of the print process.
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

1. Send an N-CREATE request to create a *Basic Film Session SOP Class*
   Instance.
2. Send an N-CREATE request to create a *Basic Film Box SOP Class* Instance
   within the *Film Session*. The SCP will also create one or more of the
   appropriate *Image Box SOP Class* Instances (*Basic Grayscale* or *Basic
   Color*) depending on the Meta SOP Class used to create the *Film Session*.
3. For each of the *Image Box SOP Class* Instances use N-SET to update its
   attributes with the image data and image attributes that are to be printed.
4. Use N-ACTION to command the *Film Box* to be printed or N-DELETE to delete
   the *Film Box*.
5. Repeat steps 2-4 as required.
6. Terminate the association to delete the *Film Session* hierarchy.


DIMSE Services Available
........................

+-----------------+---------------------+
| DIMSE-N Service | Usage SCU/SCP       |
+=================+=====================+
| Basic Film Session SOP Class          |
+-----------------+---------------------+
| N-CREATE        | Mandatory/Mandatory |
+-----------------+---------------------+
| N-SET           | Optional/Mandatory  |
+-----------------+---------------------+
| N-DELETE        | Optional/Mandatory  |
+-----------------+---------------------+
| N-ACTION        | Optional/Optional   |
+-----------------+---------------------+
| Basic Film Box SOP Class              |
+-----------------+---------------------+
| N-CREATE        | Mandatory/Mandatory |
+-----------------+---------------------+
| N-ACTION        | Mandatory/Mandatory |
+-----------------+---------------------+
| N-DELETE        | Optional/Mandatory  |
+-----------------+---------------------+
| N-SET           | Optional/Optional   |
+-----------------+---------------------+
| Basic Grayscale Image Box SOP Class   |
+-----------------+---------------------+
| N-SET           | Mandatory/Mandatory |
+-----------------+---------------------+
| Printer SOP Class                     |
+-----------------+---------------------+
| N-EVENT-REPORT  | Mandatory/Mandatory |
+-----------------+---------------------+
| N-GET           | Optional/Optional   |
+-----------------+---------------------+

Example
.......

Print the image data from a SOP Instance onto a single A4 page.

.. code-block:: python

    import sys

    from pydicom import dcmread
    from pydicom.dataset import Dataset

    from pynetdicom import AE
    from pynetdicom.sop_class import (
        BasicGrayscalePrintManagementMetaSOPClass,
        BasicFilmSessionSOPClass,
        BasicFilmBoxSOPClass,
    )

    # The SOP Instance containing the grayscale image data to be printed
    DATASET = dcmread('path/to/file.dcm')

    ae = AE()
    ae.add_requested_context(BasicGrayscalePrintManagementMetaSOPClass)

    def build_session():
        # Our Film Session N-CREATE *Attribute List*
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
        # Our Film Box N-CREATE *Attribute List*
        # The "film" consists of a single Image Box
        attr_list = Dataset()
        attr_list.ImageDisplayFormat = 'STANDARD\1,1'
        attr_list.FilmOrientation = 'PORTRAIT'
        attr_list.FilmSizeID = 'A4'

        # Can only contain a single item, is a reference to the *Film Session*
        attr_list.ReferencedFilmSessionSequence = [Dataset]
        item = ds.ReferencedFilmSessionSequence[0]
        item.ReferencedSOPClassUID = session.SOPClassUID
        item.ReferencedSOPInstanceUID = session.SOPInstanceUID

        return attr_list

    def build_image_box(im):
        """Build the *Attribute List* to be used to update the Basic Grayscale
        Image Box SOP Class* Instance.

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


    assoc = ae.associate('localhost', 11112)
    if assoc.is_established:
        # Create *Film Session*
        status, film_session = assoc.send_n_create(
            build_session(), BasicFilmSessionSOPClass, generate_uid(),
            meta_uid=BasicGrayscalePrintManagementMetaSOPClass
        )

        if not status or status.Status != 0x0000:
            print('Creation of Film Session failed, releasing association')
            assoc.release()
            sys.exit()

        print('Film Session created')
        # Create *Film Box* and *Image Box(es)*
        status, film_box = assoc.send_n_create(
            build_film_box(film_session), BasicFilmBoxSOPClass, generate_uid(),
            meta_uid=BasicGrayscalePrintManagementMetaSOPClass
        )
        if not status or status.Status != 0x0000:
            print('Failed to create the Film Box')
            assoc.release()
            sys.exit()

        print('Film Box created')
        # Update the *Image Box* with the image data
        # In this example we only have one *Image Box* per *Film Box*
        status, image_box = assoc.send_n_set(
            build_image_box(DATASET),
            film_box.SOPClassUID, film_box.SOPInstanceUID,
            meta_uid=BasicGrayscalePrintManagementMetaSOPClass
        )
        if not status or status.Status != 0x0000:
            print('Failed to update the Image Box')
            assoc.release()
            sys.exit()

        print('Updated the Image Box with the image data')

        # Print the *Film Box* and close the association
        status, action_reply = assoc.send_n_action(
            action_information, action_type,
            BasicFilmBoxSOPClass, film_box.SOPInstanceUID,
            meta_uid=BasicGrayscalePrintManagementMetaSOPClass
        )
        if not status or status.Status != 0x0000:
            print('Failed to print the Film Box')
            assoc.release()
            sys.exit()

        print('Successfully printed the Film Box')

        # Optional - Delete the Film Box
        status = assoc.send_n_delete(
            BasicFilmBoxSOPClass, film_box.SOPInstanceUID
        )

        # Close the association (also deletes the entire *Film Session*)
        assoc.release()
