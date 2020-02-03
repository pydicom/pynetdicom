"""Event handlers for qrscp.py"""


def handle_echo(event, config, app_logger):
    """Handler for evt.EVT_C_ECHO."""
    requestor = event.assoc.requestor
    timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    app_logger.info(
        "Received C-ECHO request from ({}:{}) at {}"
        .format(requestor.address, requestor.port, timestamp)
    )
    return 0x0000


def handle_find(event, config, app_logger):
    """Handler for evt.EVT_C_FIND."""
    yield 0x0000, None


def handle_get(event, config, app_logger):
    """Handler for evt.EVT_C_GET."""
    yield 0
    yield 0x0000, None


def handle_move(event, config, app_logger):
    """Handler for evt.EVT_C_MOVE."""
    yield None, None
    yield 0
    yield 0x0000, None


def handle_store(event, config, app_logger):
    """Handler for evt.EVT_C_STORE.

    Parameters
    ----------
    event : events.Event
    config : dict
    app_logger : logging.Logger
    """
    return 0x0000
