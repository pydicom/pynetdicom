#!/usr/bin/env python
"""A Verification, Storage and Query/Retrieve SCP application.


TODO:
* Add support for custom configuration file with -c option
"""

import argparse
from configparser import ConfigParser
import os
import sys

import pydicom.config
from pydicom.dataset import Dataset

from pynetdicom import (
    AE, evt, AllStoragePresentationContexts, ALL_TRANSFER_SYNTAXES
)
from pynetdicom import _config, _handlers
from pynetdicom.apps.common import setup_logging
from pynetdicom.sop_class import (
    VerificationSOPClass,
    PatientRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelMove,
    PatientRootQueryRetrieveInformationModelGet,
    StudyRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelGet
)

#from pynetdicom.apps.qrscp import config
from pynetdicom.apps.qrscp.handlers import (
    handle_echo, handle_find, handle_get, handle_move, handle_store
)

# Use `None` for empty values
pydicom.config.use_none_as_empty_text_VR_value = True
# Don't log identifiers
_config.LOG_RESPONSE_IDENTIFIERS = False

# Override the standard logging handlers
def _dont_log(event):
    pass

_handlers._send_c_find_rsp = _dont_log
_handlers._send_c_get_rsp = _dont_log
_handlers._send_c_move_rsp = _dont_log
_handlers._send_c_store_rq = _dont_log
_handlers._recv_c_store_rsp = _dont_log


__version__ = '0.0.0alpha1'


def _log_config(config, logger):
    """Log the configuration settings.

    Parameters
    ----------
    logger : logging.Logger
        The application's logger.
    """
    logger.debug('Configuration Settings')
    app = config['DEFAULT']
    logger.debug(
        '  AE title: {}, Port: {}, Max. PDU: {}'
        .format(app['ae_title'], app['port'], app['max_pdu'])
    )
    logger.debug('  Storage directory: {}'.format(app['instance_location']))
    logger.debug('  Database location: {}'.format(app['database_location']))

    if config.sections():
        logger.debug('  Move destinations: ')
    else:
        logger.debug('  Move destinations: none')

    for ae_title in config.sections():
        addr = config[ae_title]['address']
        port = config[ae_title]['port']
        logger.debug('    {}: ({}, {})'.format(ae_title, addr, port))

    logger.debug('')


def _setup_argparser():
    """Setup the command line arguments"""
    # Description
    parser = argparse.ArgumentParser(
        description=(
            "The qrscp application implements a Service Class Provider (SCP) "
            "for the Verification, Storage and Query/Retrieve (QR) Service "
            "Classes."""
        ),
        usage="qrscp [options] port"
    )

    # Parameters
    req_opts = parser.add_argument_group('Parameters')
    req_opts.add_argument("port", help="TCP/IP listen port number", type=int)

    # General Options
    gen_opts = parser.add_argument_group('General Options')
    gen_opts.add_argument(
        "--version",
        help="print version information and exit",
        action="store_true"
    )
    output = gen_opts.add_mutually_exclusive_group()
    output.add_argument(
        "-q", "--quiet",
        help="quiet mode, print no warnings and errors",
        action="store_const",
        dest='log_type', const='q'
    )
    output.add_argument(
        "-v", "--verbose",
        help="verbose mode, print processing details",
        action="store_const",
        dest='log_type', const='v'
    )
    output.add_argument(
        "-d", "--debug",
        help="debug mode, print debug information",
        action="store_const",
        dest='log_type', const='d'
    )
    gen_opts.add_argument(
        "-ll", "--log-level", metavar='[l]',
        help=(
            "use level l for the logger (critical, error, warn, info, debug)"
        ),
        type=str,
        choices=['critical', 'error', 'warn', 'info', 'debug']
    )
    fdir = os.path.abspath(os.path.dirname(__file__))
    fpath = os.path.join(fdir, 'default.ini')
    gen_opts.add_argument(
        '-c', '--config', metavar='[f]ilename',
        help="use configuration file f",
        type=str,
        default=fpath,
    )

    house_opts = parser.add_argument_group('Housekeeping Options')
    house_opts.add_argument(
        '--clean',
        help=(
            "remove all entries from the database and delete the "
            "corresponding stored instances"
        ),
        action="store_true",
    )

    return parser.parse_args()


def clean(db_path, logger):
    """Remove all entries from the database and delete the corresponding
    stored instances.

    Parameters
    ----------
    db_path : str
        The database path to use with create_engine().
    logger : logging.Logger
        The application logger.

    Returns
    -------
    bool
        ``True`` if the storage directory and database were both cleaned
        successfully, ``False`` otherwise.
    """
    engine = create_engine(db_path)
    with engine.connect() as conn:
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            fpaths = [ii.filename for ii in session.query(Instance).all()]
        except Exception as exc:
            logger.error("Exception cleaning the database")
            logger.exception(exc)
            session.rollback()
        finally:
            session.close()

        storage_cleaned = True
        for fpath in fpaths:
            try:
                os.remove(os.path.join(config.INSTANCE_LOCATION, fpath))
            except Exception as exc:
                logger.error(
                    "Unable to delete the instance at '{}'".format(fpath)
                )
                logger.exception(exc)
                storage_cleaned = False

        if storage_cleaned:
            logger.info('Storage directory cleaned successfully')
        else:
            logger.error('Failed to clean storage directory')

        database_cleaned = False
        try:
            clear(session)
            database_cleaned = True
            logger.info('Database cleaned successfully')
        except Exception as exc:
            logger.error('Failed to clean the database')
            logger.exception(exc)
            session.rollback()
        finally:
            session.close()

        return database_cleaned and storage_cleaned


def main(args=None):
    """Run the application."""
    if args is not None:
        sys.argv = args

    args = _setup_argparser()

    if args.version:
        print('qrscp.py v{}'.format(__version__))
        sys.exit()

    APP_LOGGER = setup_logging(args, 'qrscp')
    APP_LOGGER.debug('qrscp.py v{0!s}'.format(__version__))
    APP_LOGGER.debug('')

    APP_LOGGER.debug('Using configuration from {}'.format(args.config))
    APP_LOGGER.debug('')
    config = ConfigParser()
    config.read(args.config)

    # Log configuration settings
    _log_config(config, APP_LOGGER)
    app_config = config['DEFAULT']

    # Use default or specified configuration file
    current_dir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.join(current_dir, app_config['instance_location'])
    db_path = os.path.join(current_dir, app_config['database_location'])

    # The path to the database
    db_path = 'sqlite:///{}'.format(db_path)

    # Clean up the database and storage directory
    if args.clean:
        response = input(
            "This will delete all instances from both the storage directory "
            "and the database. Are you sure you wish to continue? [yes/no]: "
        )
        if response != 'yes':
            sys.exit()

        if clean(db_path, APP_LOGGER):
            sys.exit()
        else:
            sys.exit(1)

    # Try to create the instance storage directory
    os.makedirs(instance_dir, exist_ok=True)

    ae = AE(app_config['ae_title'])
    ae.maximum_pdu_size = app_config.getint('max_pdu')

    ## Add supported presentation contexts
    # Verification SCP
    ae.add_supported_context(VerificationSOPClass)

    # Storage SCP - support all transfer syntaxes
    for cx in AllStoragePresentationContexts:
        ae.add_supported_context(
            cx.abstract_syntax, ALL_TRANSFER_SYNTAXES,
            scp_role=True, scu_role=False
        )

    # Query/Retrieve SCP
    ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
    ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
    ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
    ae.add_supported_context(StudyRootQueryRetrieveInformationModelFind)
    ae.add_supported_context(StudyRootQueryRetrieveInformationModelMove)
    ae.add_supported_context(StudyRootQueryRetrieveInformationModelGet)

    # Set our handler bindings
    handlers = [
        (evt.EVT_C_ECHO, handle_echo, [args, APP_LOGGER]),
        (evt.EVT_C_FIND, handle_find, [db_path, args, APP_LOGGER]),
        (evt.EVT_C_GET, handle_get, [db_path, args, APP_LOGGER]),
        (evt.EVT_C_MOVE, handle_move, [db_path, args, APP_LOGGER]),
        (
            evt.EVT_C_STORE,
            handle_store,
            [instance_dir, db_path, args, APP_LOGGER]
        ),
    ]

    # Listen for incoming association requests
    ae.start_server(('', app_config.getint('port')), evt_handlers=handlers)


if __name__ == "__main__":
    main()
