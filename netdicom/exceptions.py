#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#


class DIMSEException:

    def __init__(self, data):
        self.data = data


class ABORT(DIMSEException):

    def __init__(self, data):
        DIMSEException.__init__(self, data)


class P_ABORT(DIMSEException):

    def __init__(self, data):
        DIMSEException.__init__(self, data)


class RELEASE(DIMSEException):

    def __init__(self, data):
        DIMSEException.__init__(self, data)
