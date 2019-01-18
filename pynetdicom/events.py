"""Module used to support Event handling."""

from datetime import datetime

"""

We want to be able to tie specific events to user callable functions as a
way to update the current AE.on_c_echo, etc, pattern.

def on_c_echo(evt):
    evt.dataset - pydicom Dataset
    evt.context - PresentationContextTupleThing
    evt.message - C-ECHO-RQ
    evt.is_cancelled() - function, returns bool
    evt.timestamp - time event occurred
    evt.type - evt.DIMSEEvent

Which implies that evt is a class instance.

ae = AE()
ae.bind(event, callable)  # AE event binding

# Association specific event binding
assoc = ae.associate(host, port, events=[???])

# Hmm, I'd like to be able tie events to specific association requestors
# as well as general events
scp = ae.start_server((host, port), events=[???])

I'd like to use the event binding system to replace the current logging methods

"""


class Event(object):
    """

    Attributes
    ----------
    timestamp : datetime.datetime
        The date/time the event was created. Will be slightly before or after
        the actual event that this object represents.
    """"
    def __init__(self):
        self.timestamp = datetime.now()
