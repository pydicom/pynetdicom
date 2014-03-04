#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

"""Starts the Offis Dicom Toolkit dcmqrscp program

dcmqrscp is useful for testing echocsu, storescu,
findscu, movescu and getscu.
"""

import os
import time
from utils import testfiles_dir

config_template = """
# Global Configuration Parametersq
NetworkType     = "tcp"
NetworkTCPPort  = %d
MaxPDUSize      = 16384
MaxAssociations = 16
Display         = "no"

HostTable BEGIN
AE2 = (AE2, localhost, 9999)
HostTable END

AETable BEGIN
%s        %s/db   RW (200, 1024mb) ANY
AETable END
"""


def start_dcmqrscp(server_port=2000, server_AET='OFFIS_AE',
                   install_dir_base='/tmp/dcmqrscp', dcmtk_base='/usr',
                   populate=False):
    """
    Starts an instance of dcmqrscp with server_port and server_AET in
    an xterm window.  The database and config file will be created in
    the directory install_dir_base/server_AET.  The dcmtk_bas
    parameter is the directory where the offis toolkit executables reside.
    It is possible to start several instances by using different ports
    and AE titles.
    """

    # clean up
    install_dir = install_dir_base + '/' + server_AET
    os.system('rm -rf %s' % install_dir)
    try:
        os.mkdir(install_dir_base)
    except:
        pass
    os.mkdir(install_dir)
    os.mkdir(install_dir + '/db')

    # create dcmqrscp configuration file base on config_template
    f = open(install_dir + '/dcmqrscp.cfg', 'w')
    f.write(config_template % (server_port, server_AET, install_dir))
    f.close()

    # start dcmqrscp in a separate window
    cmd = 'cd %s;xterm -e "%s/bin/dcmqrscp -d -c dcmqrscp.cfg;read"&' % \
        (install_dir, dcmtk_base)
    os.system(cmd)
    time.sleep(1)

    if populate:
        # populate db with a some data
        storescu_cmd = dcmtk_base + \
            '/bin/storescu localhost %d -aec %s ' % (server_port, server_AET)
        for ii in os.listdir(testfiles_dir()):
            if ii.endswith('.dcm'):
                os.system(storescu_cmd + os.path.join(testfiles_dir(), ii))


if __name__ == '__main__':
    # Start two instances of dcmqrscp.
    start_dcmqrscp(server_port=2001, server_AET='AE1', populate=True)
    #start_dcmqrscp(server_port=2002, server_AET='AE2')
