"""CLI interface for pynetdicom"""

import importlib
import sys

from pynetdicom import __version__


_APPS = {
    'echoscp': 'pynetdicom.apps.echoscp.echoscp',
    'echoscu': 'pynetdicom.apps.echoscu.echoscu',
    'findscu': 'pynetdicom.apps.findscu.findscu',
    'getscu': 'pynetdicom.apps.getscu.getscu',
    'movescu': 'pynetdicom.apps.movescu.movescu',
    'qrscp': 'pynetdicom.apps.qrscp.qrscp',
    'storescp': 'pynetdicom.apps.storescp.storescp',
    'storescu': 'pynetdicom.apps.storescu.storescu',
}


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[0] == '--version':
        print(__version__)
    else:
        app_path = _APPS[args[0]]
        app = importlib.import_module(app_path)
        app.main(args)
