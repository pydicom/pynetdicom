"""Implementation of the DIMSE Status"""


class Status(int):
    """Implementation of the DIMSE Status value.

    When sub-classing python built-ins you should only extend behaviour.
    """
    """
    DIMSE-C Statuses
    ----------------s
    C-GET - PS3.7 Section 9.1.3.1.6 and PS3.4 Annex C.4.3.1.4
    * Success - 0x0000
    * Pending - 0xFF00
    * Refused: Out of Resources, unable to calculate number of matches - 0xA701
    * Refused: Out of Resources, unable to perform sub-operations - 0xA702
    * Refused: SOP Class Not Supported
    * Cancel - 0xFE00
    * Failure: Identifier Does Not Match SOP Class - 0xA900
    * Failure: Unable to Process - 0xCxxx
    * Refused: Duplicate Invocation
    * Refused: Mistyped Argument
    * Refused: Unrecognised Operation
    * Refused: Not Authorised
    * Warning: Sub-operations complete and one or more failures/warnings - 0xB000
    """
    """
    DIMSE-N Statuses
    ----------------

    """
    """
    Statuses
    --------
    Taken from PS3.7 Annex C

    Success Status Class
    ~~~~~~~~~~~~~~~~~~~~
    Success - 0x0000

    Pending Status Class
    ~~~~~~~~~~~~~~~~~~~~
    Service Class Specific: 0xFF00 or 0xFF01

    Pending - (Service Class Specific)

    Cancel Status Class
    ~~~~~~~~~~~~~~~~~~~
    Cancel - 0xFE00

    Warning Status Class
    ~~~~~~~~~~~~~~~~~~~~
    Service Class Specific: 0x0001 or 0xBxxx
    General Annex C assigned: 0x01xx, 0x02xx

    Warning - (Service Class Specific)
    Attribute List Error - 0x0107
    Attribute Value Out of Range - 0x0116

    Failure Status Class
    ~~~~~~~~~~~~~~~~~~~~
    Service Class Specific: 0xAxxx and 0xCxxx
    General Annex C assigned: 0x01xx and 0x02xx

    Error: Cannot Understand - (Service Class Specific)
    Error: Data Set Does Not Match SOP Class - (Service Class Specific)
    Failed - (Service Class Specific)
    Refused: Move Destination Unknown - (Service Class Specific)
    Refused: Out of Resources - (Service Class Specific)
    Refused: SOP Class Not Supported - 0x0122
    Class-Instance Conflict - 0x0119
    Duplicate SOP Instance - 0x0111
    Duplicate Invocation - 0x0210
    Invalid Argument Value - 0x0115
    Invalid Attribute Value - 0x0106
    Invalid Object Instance - 0x0117
    Missing Attribute - 0x0120
    Missing Attribute Value - 0x0121
    Mistyped Argument - 0x0212
    No Such Argument - 0x0114
    No Such Attribute - 0x0105
    No Such Event Type - 0x0113
    No Such SOP Instance - 0x0112
    No Such SOP Class - 0x0118
    Processing Failure - 0x0110
    Resources Limitation - 0x0213
    Unrecognised Operation - 0x0211
    No Such Action Type - 0x0123
    Refused: Not Authorised - 0x0124
    """
    def __new__(cls, val, category, name, description=''):
        cls.description = description
        cls.name = name
        cls.category = category
        return super(Status, cls).__new__(cls, val)

    def __str__(self):
        return '0x{0:04x}'.format(self)


GENERAL_STATUS = {0x0000 : ('Success', ''),
                  0xFE00 : ('Cancel', ''),
                  0x0107 : ('Warning', 'Attribute List Error'),
                  0x0116 : ('Warning', 'Attribute Value Out of Range'),
                  0x0122 : ('Failure', 'Refused: SOP Class Not Supported'),
                  0x0119 : ('Failure', 'Class-Instance Conflict'),
                  0x0111 : ('Failure', 'Duplication SOP Instance'),
                  0x0210 : ('Failure', 'Duplicate Invocation'),
                  0x0115 : ('Failure', 'Invalid Argument Value'),
                  0x0106 : ('Failure', 'Invalid Attribute Value'),
                  0x0117 : ('Failure', 'Invalid Object Instance'),
                  0x0120 : ('Failure', 'Missing Attribute'),
                  0x0121 : ('Failure', 'Missing Attribute Value'),
                  0x0212 : ('Failure', 'Mistyped Argument'),
                  0x0114 : ('Failure', 'No Such Argument'),
                  0x0105 : ('Failure', 'No Such Attribute'),
                  0x0113 : ('Failure', 'No Such Event Type'),
                  0x0112 : ('Failure', 'No Such SOP Instance'),
                  0x0118 : ('Failure', 'No Such SOP Class'),
                  0x0110 : ('Failure', 'Processing Failure'),
                  0x0213 : ('Failure', 'Resources Limitation'),
                  0x0211 : ('Failure', 'Unrecognised Operation'),
                  0x0123 : ('Failure', 'No Such Action'),
                  0x0124 : ('Failure', 'Refused: Not Authorised')}

def code_to_status(val):
    if val in GENERAL_STATUS:
        return Status(val, *GENERAL_STATUS[val])

    return None
