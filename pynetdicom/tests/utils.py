import time


def sleep(duration):
    """Sleep for at least `duration` seconds."""
    now = time.perf_counter()
    end = now + duration
    while now < end:
        now = time.perf_counter()


def wait_for_server_socket(server, timeout=5):
    """Sleep until the AssociationServer's socket is bound to an address.

    Parameters
    ----------
    server : pynetdicom.transport.AssociationServer
        The server that we're waiting on.
    timeout : int or float, optional
        The maximum number of seconds to wait for.
    """
    # TODO: Python >= 3.8: use sys.audit() instead
    timeout = 0
    while timeout < 1:
        try:
            assert server.socket.getsockname() != ("0.0.0.0", 0)
            return
        except AssertionError:
            time.sleep(0.05)
            timeout += 0.05
