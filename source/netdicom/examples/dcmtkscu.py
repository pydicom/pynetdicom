#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

"""Utility to launch various dcmtk clients for testing purposes
"""
 
import os


def run_in_term(cmd):
     # start dcmqrscp in a separate window
    cmd =  'xterm -e "(sleep 2;%s)" &' % (cmd)
    print os.system(cmd)   
