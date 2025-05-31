
.. currentmodule:: pynetdicom.events

Event Handlers
..............

Event handlers are callable functions bound to an event that, at a minimum,
get passed a single parameter, *event*, which is an :class:`Event` instance.
All :class:`Event` instances come with at least three attributes:

* :attr:`Event.assoc` - the
  :class:`Association <pynetdicom.association.Association>` in which the
  event occurred
* :attr:`Event.event` - the corresponding event, as a Python
  :func:`namedtuple<collections.namedtuple>`
* :attr:`Event.timestamp` - the date and time the event occurred at, as a
  Python :class:`datetime.datetime`

Additional attributes and properties are available depending on the event type,
see the `handler implementation documentation
<../reference/events.html>`_ for more information.

Handlers can be bound to events through the *evt_handlers* keyword parameter
with :meth:`AE.associate()<pynetdicom.ae.ApplicationEntity.associate>` and
:meth:`AE.start_server()<pynetdicom.ae.ApplicationEntity.start_server>`.
*evt_handlers* should be a list of 2- or 3-tuples::

    from pynetdicom import evt, AE
    from pynetdicom.sop_class import Verification, CTImageStorage

    def handle_echo(event):
        # Because we used a 2-tuple to bind `handle_echo` we
        #   have no extra parameters
        return 0x0000

    def handle_store(event, arg1, arg2):
        # Because we used a 3-tuple to bind `handle_store` we
        #   have optional extra parameters
        assert arg1 == 'optional'
        assert arg2 == 'parameters'
        return 0x0000

    handlers = [
        (evt.EVT_C_ECHO, handle_echo),
        (evt.EVT_C_STORE, handle_store, ['optional', 'parameters']),
    ]

    ae = AE()
    ae.add_supported_context(Verification)
    ae.add_supported_context(CTImageStorage)
    ae.start_server(("127.0.0.1", 11112), evt_handlers=handlers)

If using a 3-tuple then the third item should be a list of objects that will
be passed to the handler as extra parameters.

The other way to bind handlers to events is through the
:meth:`Association.bind()<pynetdicom.association.Association.bind>` and
:meth:`AssociationServer.bind()
<pynetdicom.transport.AssociationServer.bind>` methods. Handlers can be
unbound with
:class:`Association.unbind()<pynetdicom.association.Association.unbind>` and
:class:`AssociationServer.unbind()<pynetdicom.transport.AssociationServer>`
methods. See the :doc:`Association<association_accepting>` guide for more details.
