"""Event handlers for qrscp.py"""


def handle_echo(event, config, logger):
    """Handler for evt.EVT_C_ECHO.

    Parameters
    ----------
    event : events.Event
        The corresponding event.
    config : dict
        A dict containing configuration settings.
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


def handle_find(event, config, logger):
    """Handler for evt.EVT_C_FIND."""
    yield 0x0000, None


def handle_get(event, config, logger):
    """Handler for evt.EVT_C_GET."""
    yield 0
    yield 0x0000, None


def handle_move(event, config, logger):
    """Handler for evt.EVT_C_MOVE."""
    yield None, None
    yield 0
    yield 0x0000, None


def handle_store(event, config, logger):
    """Handler for evt.EVT_C_STORE."""
    return 0x0000
