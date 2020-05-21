"""Event handlers for qrscp.py"""

import os

from pydicom import dcmread

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from . import config
from .db import add_instance, search, InvalidIdentifier, Instance


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
        finally:
            session.close()

        # Yield number of sub-operations
        yield len(matches)

        # Yield results
        for match in matches:
            if event.is_cancelled:
                yield 0xFE00, None
                return

            db_dir = os.path.dirname(config.DATABASE_LOCATION)
            ds = dcmread(os.path.join(db_dir, match.filename))
            yield 0xFF00, ds


def handle_move(event, db_path, cli_config, logger):
    """Handler for evt.EVT_C_MOVE.

    Parameters
    ----------
    event : pynetdicom.events.Event
        The C-MOVE request :class:`~pynetdicom.events.Event`.
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
    if event.move_destination not in config.MOVE_DESTINATIONS:
        logger.info('No matching move destination in config.MOVE_DESTINATIONS')
        yield None, None
        return

    # Yield `Move Destination` IP and port
    yield config.MOVE_DESTINATIONS[event.move_destination]

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
        finally:
            session.close()

        # Yield number of sub-operations
        yield len(matches)

        # Determine the presentation contexts required for the matches
        event.assoc.ae.requested_contexts = _get_contexts(matches)

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
    fpath = os.path.join(config.INSTANCE_LOCATION, sop_instance)
    db_dir = os.path.dirname(config.DATABASE_LOCATION)

    if os.path.exists(fpath):
        logger.warning(
            'Instance already exists in storage directory, overwriting'
        )

    try:
        ds.save_as(fpath, write_like_original=False)
    except IOError as exc:
        logger.error('Failed writing instance to storage directory')
        logger.exception(exc)
        # Failed - Out of Resources - IOError
        return 0xA700
    except Exception as exc:
        logger.error('Failed writing instance to storage directory')
        logger.exception(exc)
        # Failed - Out of Resources - Miscellaneous error
        return 0xA701

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
            add_instance(ds, session, os.path.relpath(fpath, db_dir))
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
