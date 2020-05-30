"""Event handlers for qrscp.py"""

import os

from pydicom import dcmread

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pynetdicom.apps.qrscp.db import (
    add_instance, search, InvalidIdentifier, Instance
)


def handle_echo(event, cli_config, logger):
    """Handler for evt.EVT_C_ECHO.

    Parameters
    ----------
    event : events.Event
        The corresponding event.
    cli_config : dict
        A :class:`dict` containing configuration settings passed via CLI.
    logger : logging.Logger
        The application's logger.

    Returns
    -------
    int
        The status of the C-ECHO operation, always ``0x0000`` (Success).
    """
    requestor = event.assoc.requestor
    timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(
        "Received C-ECHO request from {}:{} at {}"
        .format(requestor.address, requestor.port, timestamp)
    )

    return 0x0000


def handle_find(event, db_path, cli_config, logger):
    """Handler for evt.EVT_C_FIND.

    Parameters
    ----------
    event : pynetdicom.events.Event
        The C-FIND request :class:`~pynetdicom.events.Event`.
    db_path : str
        The database path to use with create_engine().
    cli_config : dict
        A :class:`dict` containing configuration settings passed via CLI.
    logger : logging.Logger
        The application's logger.

    Yields
    ------
    int or pydicom.dataset.Dataset, pydicom.dataset.Dataset or None
        The C-FIND response's *Status* and if the *Status* is pending then
        the dataset to be sent, otherwise ``None``.
    """
    requestor = event.assoc.requestor
    timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(
        "Received C-FIND request from {}:{} at {}"
        .format(requestor.address, requestor.port, timestamp)
    )

    model = event.request.AffectedSOPClassUID

    engine = create_engine(db_path)
    with engine.connect() as conn:
        Session = sessionmaker(bind=engine)
        session = Session()
        # Search database using Identifier as the query
        try:
            matches = search(model, event.identifier, session)
        except InvalidIdentifier as exc:
            session.rollback()
            logger.error('Invalid C-FIND Identifier received')
            logger.error(str(exc))
            yield 0xA900, None
            return
        except Exception as exc:
            session.rollback()
            logger.error('Exception occurred while querying database')
            logger.exception(exc)
            yield 0xC320, None
            return
        finally:
            session.close()

    # Yield results
    for match in matches:
        if event.is_cancelled:
            yield 0xFE00, None
            return

        try:
            response = match.as_identifier(event.identifier, model)
            response.RetrieveAETitle = event.assoc.ae.ae_title
        except Exception as exc:
            logger.error("Error creating response Identifier")
            logger.exception(exc)
            yield 0xC322, None

        yield 0xFF00, response


def handle_get(event, db_path, cli_config, logger):
    """Handler for evt.EVT_C_GET.

    Parameters
    ----------
    event : pynetdicom.events.Event
        The C-GET request :class:`~pynetdicom.events.Event`.
    db_path : str
        The database path to use with create_engine().
    cli_config : dict
        A :class:`dict` containing configuration settings passed via CLI.
    logger : logging.Logger
        The application's logger.

    Yields
    ------
    int
        The number of sub-operations required to complete the request.
    int or pydicom.dataset.Dataset, pydicom.dataset.Dataset or None
        The C-GET response's *Status* and if the *Status* is pending then
        the dataset to be sent, otherwise ``None``.
    """
    requestor = event.assoc.requestor
    timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(
        "Received C-GET request from {}:{} at {}"
        .format(requestor.address, requestor.port, timestamp)
    )

    model = event.request.AffectedSOPClassUID

    engine = create_engine(db_path)
    with engine.connect() as conn:
        Session = sessionmaker(bind=engine)
        session = Session()
        # Search database using Identifier as the query
        try:
            matches = search(model, event.identifier, session)
        except InvalidIdentifier as exc:
            session.rollback()
            logger.error('Invalid C-GET Identifier received')
            logger.error(str(exc))
            yield 0xA900, None
            return
        except Exception as exc:
            session.rollback()
            logger.error('Exception occurred while querying database')
            logger.exception(exc)
            yield 0xC420, None
            return
        finally:
            session.close()

    # Yield number of sub-operations
    yield len(matches)

    # Yield results
    for match in matches:
        if event.is_cancelled:
            yield 0xFE00, None
            return

        try:
            ds = dcmread(match.filename)
        except Exception as exc:
            logger.error("Error reading file: {}".format(fpath))
            logger.exception(exc)
            yield 0xC421, None

        yield 0xFF00, ds


def handle_move(event, destinations, db_path, cli_config, logger):
    """Handler for evt.EVT_C_MOVE.

    Parameters
    ----------
    event : pynetdicom.events.Event
        The C-MOVE request :class:`~pynetdicom.events.Event`.
    destinations : dict
        A :class:`dict` containing know move destinations as
        ``{b'AE_TITLE: (addr, port)}``
    db_path : str
        The database path to use with create_engine().
    cli_config : dict
        A :class:`dict` containing configuration settings passed via CLI.
    logger : logging.Logger
        The application's logger.

    Yields
    ------
    (str, int) or (None, None)
        The (IP address, port) of the *Move Destination* (if known).
    int
        The number of sub-operations required to complete the request.
    int or pydicom.dataset.Dataset, pydicom.dataset.Dataset or None
        The C-MOVE response's *Status* and if the *Status* is pending then
        the dataset to be sent, otherwise ``None``.
    """
    requestor = event.assoc.requestor
    timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(
        "Received C-MOVE request from {}:{} at {} with move destination {}"
        .format(
            requestor.address,
            requestor.port,
            timestamp,
            event.move_destination
        )
    )

    # Unknown `Move Destination`
    try:
        addr, port = destinations[event.move_destination]
    except KeyError:
        logger.info('No matching move destination in the configuration')
        yield None, None
        return

    model = event.request.AffectedSOPClassUID
    engine = create_engine(db_path)
    with engine.connect() as conn:
        Session = sessionmaker(bind=engine)
        session = Session()
        # Search database using Identifier as the query
        try:
            matches = search(model, event.identifier, session)
        except InvalidIdentifier as exc:
            session.rollback()
            logger.error('Invalid C-MOVE Identifier received')
            logger.error(str(exc))
            yield 0xA900, None
            return
        except Exception as exc:
            session.rollback()
            logger.error('Exception occurred while querying database')
            logger.exception(exc)
            yield 0xC520, None
            return
        finally:
            session.close()

    # Yield `Move Destination` IP and port, plus required contexts
    # We should be able to reduce the number of contexts by using the
    # implicit context conversion between:
    #   implicit VR <-> explicit VR <-> deflated transfer syntaxes
    contexts = list(set([ii.context for ii in matches]))
    yield addr, port, {'contexts' : contexts[:128]}

    # Yield number of sub-operations
    yield len(matches)

    # Yield results
    for match in matches:
        if event.is_cancelled:
            yield 0xFE00, None
            return

        try:
            ds = dcmread(match.filename)
        except Exception as exc:
            logger.error("Error reading file: {}".format(fpath))
            logger.exception(exc)
            yield 0xC521, None

        yield 0xFF00, ds


def handle_store(event, storage_dir, db_path, cli_config, logger):
    """Handler for evt.EVT_C_STORE.

    Parameters
    ----------
    event : pynetdicom.events.Event
        The C-STORE request :class:`~pynetdicom.events.Event`.
    storage_dir : str
        The path to the directory where instances will be stored.
    db_path : str
        The database path to use with create_engine().
    cli_config : dict
        A :class:`dict` containing configuration settings passed via CLI.
    logger : logging.Logger
        The application's logger.

    Returns
    -------
    int or pydicom.dataset.Dataset
        The C-STORE response's *Status*. If the storage operation is successful
        but the dataset couldn't be added to the database then the *Status*
        will still be ``0x0000`` (Success).
    """
    requestor = event.assoc.requestor
    timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(
        "Received C-STORE request from {}:{} at {}"
        .format(requestor.address, requestor.port, timestamp)
    )

    try:
        ds = event.dataset
        # Remove any Group 0x0002 elements that may have been included
        ds = ds[0x00030000:]
        sop_instance = ds.SOPInstanceUID
    except Exception as exc:
        logger.error("Unable to decode the dataset")
        logger.exception(exc)
        # Unable to decode dataset
        return 0xC210

    # Add the file meta information elements - must be before adding to DB
    ds.file_meta = event.file_meta

    logger.info("SOP Instance UID '{}'".format(sop_instance))

    # Try and add the instance to the database
    #   If we fail then don't even try to store
    fpath = os.path.join(storage_dir, sop_instance)
    db_dir = os.path.dirname(db_path)

    if os.path.exists(fpath):
        logger.warning(
            'Instance already exists in storage directory, overwriting'
        )

    try:
        ds.save_as(fpath, write_like_original=False)
    except Exception as exc:
        logger.error('Failed writing instance to storage directory')
        logger.exception(exc)
        # Failed - Out of Resources
        return 0xA700

    logger.info("Instance written to storage directory")

    # Dataset successfully written, try to add to/update database
    engine = create_engine(db_path)
    with engine.connect() as conn:
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            # Path is relative to the database file
            matches = session.query(Instance).filter(
                Instance.sop_instance_uid == ds.SOPInstanceUID
            ).all()
            add_instance(ds, session, os.path.abspath(fpath))
            if not matches:
                logger.info("Instance added to database")
            else:
                logger.info("Database entry for instance updated")
        except Exception as exc:
            session.rollback()
            logger.error('Unable to add instance to the database')
            logger.exception(exc)
        finally:
            session.close()

    return 0x0000
