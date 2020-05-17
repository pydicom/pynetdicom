"""Event handlers for qrscp.py"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pynetdicom.dsutils import pretty_dataset

from . import config
from .db import (
    add_instance, search, remove_instance, InvalidIdentifier, connect
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
        The path to use with create_engine().
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
        finally:
            session.close()

        # Yield results
        for match in matches:
            if event.is_cancelled:
                yield 0xFE00, None
                return

            response = match.as_identifier(event.identifier, model)
            response.RetrieveAETitle = event.assoc.ae.ae_title
            yield 0xFF00, response


def handle_get(event, session, cli_config, logger):
    """Handler for evt.EVT_C_GET.

    Parameters
    ----------
    event : pynetdicom.events.Event
        The C-GET request :class:`~pynetdicom.events.Event`.
    session : sqlalchemy.orm.Session
        A database session.
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

    # Log query dataset
    if config.LOG_IDENTIFIERS:
        logging.info('')
        for line in pretty_dataset(event.identifier):
            logging.info(line)

    # Search database using Identifier as the query
    results = search(
        event.request.AffectedSOPClassUID, event.identifier, session
    )

    # Yield number of sub-operations
    yield len(results)

    # Yield results
    for response in results:
        yield 0xFF00, response


def handle_move(event, session, cli_config, logger):
    """Handler for evt.EVT_C_MOVE.

    Parameters
    ----------
    event : pynetdicom.events.Event
        The C-MOVE request :class:`~pynetdicom.events.Event`.
    session : sqlalchemy.orm.Session
        A database session.
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
    if event.move_destination not in config.MOVE_DESTINATIONS:
        logger.info('No matching move destination in config.MOVE_DESTINATIONS')
        yield None, None
        return

    # Yield `Move Destination` IP and port
    yield config.MOVE_DESTINATIONS[event.move_destination]

    # Log query dataset
    if config.LOG_IDENTIFIERS:
        logging.info('')
        for line in pretty_dataset(event.identifier):
            logging.info(line)

    # Search database using Identifier as the query
    model = event.request.AffectedSOPClassUID
    try:
        matches = search(model, event.identifier, session)
    except InvalidIdentifier as exc:
        logger.error('Invalid C-MOVE Identifier received')
        logger.error(str(exc))
        yield 0xA900, None
        return

    # Yield number of sub-operations
    yield len(matches)

    # Yield results
    for match in matches:
        if event.is_cancelled:
            yield 0xFE00, None
            return

        ds = dcmread(match.filename)
        yield 0xFF00, ds


def handle_store(event, db_path, cli_config, logger):
    """Handler for evt.EVT_C_STORE.

    Parameters
    ----------
    event : pynetdicom.events.Event
        The C-STORE request :class:`~pynetdicom.events.Event`.
    db_path : str
        The path to use with create_engine().
    cli_config : dict
        A :class:`dict` containing configuration settings passed via CLI.
    logger : logging.Logger
        The application's logger.

    Returns
    -------
    int or pydicom.dataset.Dataset
        The C-STORE response's *Status*.
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
    fpath = os.path.join(config.INSTANCE_LOCATION, sop_instance)
    db_dir = os.path.dirname(config.DATABASE_LOCATION)

    engine = create_engine(db_path)
    with engine.connect() as conn:
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            # Path is relative to the database file
            add_instance(ds, session, os.path.relpath(fpath, db_dir))
            logger.info("Instance added to database")
        except Exception as exc:
            session.rollback()
            logger.error('Unable to add instance to the database')
            logger.exception(exc)
            return 0xC001
        finally:
            session.close()

    already_exists = False
    if os.path.exists(fpath):
        already_exists = True
        logger.warning(
            'Instance already exists in storage directory, overwriting'
        )

    try:
        ds.save_as(fpath, write_like_original=False)
        status = 0x0000
    except IOError as exc:
        logger.error('Failed writing instance to storage directory')
        logger.exception(exc)
        # Failed - Out of Resources - IOError
        status =  0xA700
    except Exception as exc:
        logger.error('Failed writing instance to storage directory')
        logger.exception(exc)
        # Failed - Out of Resources - Miscellaneous error
        status =  0xA701

    if status == 0x0000:
        logger.info("Instance written to storage directory")
    elif not already_exists:
        # Failed to save, remove from database only if not already successful
        remove_instance(ds.SOPInstanceUID, session)
        logger.debug("Instance removed from database due to store failure")
        status = 0xC002

    return status
