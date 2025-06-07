import os
import socket
import time


PORTS = {None: (11112, 11113)}


def get_port(src: str = "local") -> int:
    """Return a probably-open port that each worker can use"""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER")
    if worker_id in PORTS:
        return PORTS[worker_id][0] if src == "local" else PORTS[worker_id][1]

    # local, peer
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as l:
        l.bind(("localhost", 0))
        l.listen(1)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as r:
            r.bind(("localhost", 0))
            r.listen(1)

            PORTS[worker_id] = (l.getsockname()[1], r.getsockname()[1])

    return get_port(src)


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
