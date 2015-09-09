"""Run example scripts with the various PEERs running on the Dicom Test
Server VM."""

import test_config
import os
from utils import set_path

set_path()

script_dir = '../examples'


# storescu
cmd_template = '%s/storescu.py -aet %s -aec %s -implicit %s %d %s'
for pp in test_config.peers:
    files = '/data/PatientsTests/0008-Prostate_1/*'
    cmd = cmd_template % (script_dir, test_config.AET,
                          pp['aet'], pp['host'], pp['port'], files)
    print cmd
    os.system(cmd)
