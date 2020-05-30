"""Database interface for the qrscp application.

Unique Keys
-----------
* At each level one attribute is unique
* A unique key shall uniquely identify a single instance at a given level
* Unique keys **may** be in a C-FIND request's Identifier
* Unique keys **shall** be in a C-MOVE or C-GET request's Identifier
* C-FIND, C-GET and C-MOVE shall support existence and matching of all
* unique keys. All instances managed shall have specific non-zero length
  unique key values

Required Keys
-------------
* Multiple instances may have the same value for required keys.
* Required keys may be in a C-FIND request's Identifier
* Required keys shall not be in a C-GET or C-MOVE request's Identifier
"""

from collections import OrderedDict

try:
    import sqlalchemy
except ImportError:
    sys.exit("qrscp requires the sqlalchemy package")

from sqlalchemy import (
    create_engine, Column, ForeignKey, Integer, String
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from pydicom.dataset import Dataset

from pynetdicom import build_context
from pynetdicom.sop_class import(
    PatientRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelMove,
    PatientRootQueryRetrieveInformationModelGet,
    StudyRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelGet
)


class InvalidIdentifier(Exception):
    pass

# C.2.2.2: The total length of the attribute may be larger than given in Part 5
# C.2.2.2: The VM may be larger than the VM from Part 6, depending
#   on the matching type

# VRs for supported elements - Part 5
# CS - 16 bytes maximum - str
# DA - 8 bytes fixed, format YYYYMMDD - str
# IS - 12 bytes maximum, range - int
# LO - 64 characters maximum - str
# PN - 64 characters maximum per component group (5 components per group) - str
# SH - 16 characters maximum - str
# TM - 14 bytes maximum, format HHMMSS.FFFFFF - str
# UI - 64 bytes maximum - str


# Translate from the element keyword to the db attribute
_TRANSLATION = {
    'PatientID' : 'patient_id',  # PATIENT | Unique | VM 1 | LO
    'PatientName' : 'patient_name',  # PATIENT | Required | VM 1 | PN
    'StudyInstanceUID' : 'study_instance_uid',  # STUDY | Unique | VM 1 | UI
    'StudyDate' : 'study_date',  # STUDY | Required | VM 1 | DA
    'StudyTime' : 'study_time',  # STUDY | Required | VM 1 | TM
    'AccessionNumber' : 'accession_number',  # STUDY | Required | VM 1 | SH
    'StudyID' : 'study_id',  # STUDY | Required | VM 1 | SH
    'SeriesInstanceUID' : 'series_instance_uid',  # SERIES | Unique | VM 1 | UI
    'Modality' : 'modality',  # SERIES | Required | VM 1 | CS
    'SeriesNumber' : 'series_number',  # SERIES | Required | VM 1 | IS
    'SOPInstanceUID' : 'sop_instance_uid',  # IMAGE | Unique | VM 1 | UI
    'InstanceNumber' : 'instance_number',  # IMAGE | Required | VM 1 | IS
}

# Unique and required keys and their level, VR and VM for Patient Root
# Study Root is the same but includes the PATIENT attributes
_ATTRIBUTES = {
    'PatientID' : ('PATIENT', 'U', 'LO', 1),
    'PatientName' : ('PATIENT', 'R', 'PN', 1),
    'StudyInstanceUID' : ('STUDY', 'U', 'UI', 1),
    'StudyDate' : ('STUDY', 'R', 'DA', 1),
    'StudyTime' : ('STUDY', 'R', 'TM', 1),
    'AccessionNumber' : ('STUDY', 'R', 'SH', 1),
    'StudyID' : ('STUDY', 'R', 'SH', 1),
    'SeriesInstanceUID' : ('SERIES', 'U', 'UI', 1),
    'Modality' : ('SERIES', 'R', 'VS', 1),
    'SeriesNumber' : ('SERIES', 'R', 'IS', 1),
    'SOPInstanceUID' : ('IMAGE', 'U', 'UI', 1),
    'InstanceNumber' : ('IMAGE', 'R', 'UI', 1),
}
_PATIENT_ROOT_ATTRIBUTES = OrderedDict({
    'PATIENT' : ['PatientID', 'PatientName'],
    'STUDY' : [
        'StudyInstanceUID', 'StudyDate', 'StudyTime', 'AccessionNumber',
        'StudyID'
    ],
    'SERIES' : ['SeriesInstanceUID', 'Modality', 'SeriesNumber'],
    'IMAGE' : ['SOPInstanceUID', 'InstanceNumber'],
})
_STUDY_ROOT_ATTRIBUTES = OrderedDict({
    'STUDY' : [
        'StudyInstanceUID', 'StudyDate', 'StudyTime', 'AccessionNumber',
        'StudyID', 'PatientID', 'PatientName'
    ],
    'SERIES' : ['SeriesInstanceUID', 'Modality', 'SeriesNumber'],
    'IMAGE' : ['SOPInstanceUID', 'InstanceNumber'],
})

# Supported Information Models
_C_FIND = [
    PatientRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelFind
]
_C_GET = [
    PatientRootQueryRetrieveInformationModelGet,
    StudyRootQueryRetrieveInformationModelGet
]
_C_MOVE = [
    PatientRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelMove
]

_PATIENT_ROOT = {
    PatientRootQueryRetrieveInformationModelFind : _PATIENT_ROOT_ATTRIBUTES,
    PatientRootQueryRetrieveInformationModelGet : _PATIENT_ROOT_ATTRIBUTES,
    PatientRootQueryRetrieveInformationModelMove : _PATIENT_ROOT_ATTRIBUTES,
}
_STUDY_ROOT = {
    StudyRootQueryRetrieveInformationModelFind : _STUDY_ROOT_ATTRIBUTES,
    StudyRootQueryRetrieveInformationModelGet : _STUDY_ROOT_ATTRIBUTES,
    StudyRootQueryRetrieveInformationModelMove : _STUDY_ROOT_ATTRIBUTES,
}


def add_instance(ds, session, fpath=None):
    """Add a SOP Instance to the database or update existing instance.

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        The SOP Instance to be added to the database.
    session : sqlalchemy.orm.session.Session
        The session we are using to query the database.
    fpath : str, optional
        The path to where the SOP Instance is stored, taken relative
        to the database file.
    """
    # Check if instance is already in the database
    result = session.query(Instance).filter(
        Instance.sop_instance_uid == ds.SOPInstanceUID
    ).all()
    if result:
        instance = result[0]
        instance_exists = True
    else:
        instance = Instance()
        instance_exists = False

    # Unique or Required attributes
    required = [
        # (Instance attribute, DICOM keyword, max length, req'd)
        ('patient_id', 'PatientID', 16, True),
        ('patient_name', 'PatientName', 64, False),
        ('study_instance_uid', 'StudyInstanceUID', 64, True),
        ('study_date', 'StudyDate', 8, False),
        ('study_time', 'StudyTime', 14, False),
        ('accession_number', 'AccessionNumber', 16, False),
        ('study_id', 'StudyID', 16, False),
        ('series_instance_uid', 'SeriesInstanceUID', 64, True),
        ('modality', 'Modality', 16, False),
        ('series_number', 'SeriesNumber', None, False),
        ('sop_instance_uid', 'SOPInstanceUID', 64, True),
        ('instance_number', 'InstanceNumber', None, False),
    ]

    # Unique and Required attributes
    for attr, keyword, max_len, unique in required:
        if not unique and keyword not in ds:
            value = None
        else:
            elem = ds[keyword]
            value = elem.value

        if value is not None:
            # All supported attributes have VM 1
            #assert elem.VM == 1
            if max_len:
                if elem.VR == 'PN':
                    value = str(value)

                assert len(value) <= max_len
            else:
                assert -2**31 <= value <= 2**31 - 1

        setattr(instance, attr, value)

    instance.filename = fpath

    # Transfer Syntax UID
    try:
        tsyntax = ds.file_meta.TransferSyntaxUID
        if tsyntax:
            assert len(tsyntax) < 64
            instance.transfer_syntax_uid = tsyntax
    except (AttributeError, AssertionError) as exc:
        pass

    # SOP Class UID
    try:
        uid = ds.SOPClassUID
        if uid:
            assert len(uid) < 64
            instance.sop_class_uid = uid
    except (AttributeError, AssertionError):
        pass

    session.add(instance)
    session.commit()


def build_query(identifier, session, query=None):
    """Perform a query against the database.

    Parameters
    ----------
    identifier : pydicom.dataset.Dataset
        The request's *Identifier* dataset containing the query attributes.
    session : sqlalchemy.orm.session.Session
        The session we are using to query the database.
    query : sqlalchemy.orm.query.Query, optional
        If not used then start a new query, otherwise extend the existing
        `query`.

    Returns
    -------
    sqlalchemy.orm.query.Query
        The resulting query.
    """
    # VRs for Single Value Matching and Wild Card Matching
    _text_vr = [
        'AE', 'CS', 'LO', 'LT', 'PN', 'SH', 'ST', 'UC', 'UR', 'UT'
    ]
    for elem in [e for e in identifier if e.keyword in _ATTRIBUTES]:
        vr = elem.VR
        val = elem.value
        # Convert PersonName3 to str
        if vr == 'PN' and val: val = str(val)

        # Part 4, C.2.2.2.1 Single Value Matching
        if vr != 'SQ' and val is not None:
            if vr in _text_vr and ('*' in val or '?' in val):
                pass
            elif vr in ['DA', 'TM', 'DT'] and '-' in val:
                pass
            else:
                #print('Performing single value matching...')
                query = _search_single_value(elem, session, query)
                continue

        # Part 4, C.2.2.2.3 Universal Matching
        if val is None:
            #print('Performing universal matching...')
            query = _search_universal(elem, session, query)
            continue

        # Part 4, C.2.2.2.2 List of UID Matching
        if vr == 'UI':
            #print('Performing list of UID matching...')
            query = _search_uid_list(elem, session, query)
            continue

        # Part 4, C.2.2.2.4 Wild Card Matching
        if vr in _text_vr and ('*' in val or '?' in val):
            #print('Performing wildcard matching...')
            query = _search_wildcard(elem, session, query)
            continue

        # Part 4, C.2.2.2.5 Range Matching
        if vr in ['DT', 'TM', 'DA'] and '-' in val:
            query = _search_range(elem, session, query)
            continue

        # Part 4, C.2.2.2.6 Sequence Matching
        #   No supported attributes are sequences

    return query


def _check_identifier(identifier, model):
    """Check that the C-FIND, C-GET or C-MOVE `identifier` is valid.

    Parameters
    ----------
    identifier : pydicom.dataset.Dataset
        The *Identifier* dataset to check.
    model : pydicom.uid.UID
        The Query/Retrieve Information Model.

    Raises
    ------
    InvalidIdentifier
        If the Identifier is invalid.
    """
    # Part 4, C.4.1.1.3.1, C.4.2.1.4 and C.4.3.1.3.1:
    #   (0008,0052) Query Retrieve Level is required in the Identifier
    if 'QueryRetrieveLevel' not in identifier:
        raise InvalidIdentifier(
            "The Identifier contains no Query Retrieve Level element"
        )

    if model in _PATIENT_ROOT:
        attr = _PATIENT_ROOT[model]
    else:
        attr = _STUDY_ROOT[model]

    levels = list(attr.keys())
    if identifier.QueryRetrieveLevel not in levels:
        raise InvalidIdentifier(
            "The Identifier's Query Retrieve Level value is invalid"
        )

    if len(identifier) == 1:
        raise InvalidIdentifier("The Identifier contains no keys")

    for ii, level in enumerate(levels):
        if level == identifier.QueryRetrieveLevel:
            # Check if identifier has elements below current level
            for sublevel in levels[ii + 1:]:
                if any([kw in identifier for kw in attr[sublevel]]):
                    raise InvalidIdentifier(
                        "The Identifier contains keys below the level "
                        "specified by the Query Retrieve Level"
                    )

            # The level is the same as that in the identifier so we're OK
            return

        # The level is above that in the identifier so make sure the unique
        #   keyword is present
        if attr[level][0] not in identifier:
            raise InvalidIdentifier(
                "The Identifier is missing a unique key for the '{}' level"
                .format(level)
            )


def clear(session):
    """Delete all entries from the database.

    Parameters
    ----------
    session : sqlalchemy.orm.session.Session
        The session we are using to clear the database.
    """
    for instance in session.query(Instance).all():
        session.delete(instance)

    session.commit()


def create(db_location, echo=False):
    """Create a new database at `db_location` if one doesn't already exist.

    Parameters
    ----------
    db_location : str
        The location of the database.
    echo : bool, optional
        Turn the sqlalchemy logging on (default ``False``).
    """
    engine = create_engine(db_location, echo=echo)

    # Create the tables (won't recreate tables already present)
    Base.metadata.create_all(engine)

    return engine


def remove_instance(instance_uid, session):
    """Remove a SOP Instance from the database.

    Parameters
    ----------
    instance_uid : pydicom.uid.UID
        The (0008,0018) *SOP Instance UID* of the SOP Instance to be removed
        from the database.
    session : sqlalchemy.orm.session.Session
        The session to use when querying the database for the instance.
    """
    matches = session.query(Instance).filter(
        Instance.sop_instance_uid == instance_uid
    ).all()
    if matches:
        session.delete(matches[0])
        session.commit()


def search(model, identifier, session):
    """Search the database.

    Optional keys are not supported.

    Parameters
    ----------
    model : pydicom.uid.UID
        The Query/Retrieve Information Model. Supported models are:

        - *Patient Root Query Retrieve Information Model* for C-FIND, C-GET
          and C-MOVE
        - *Study Root Query Retrieve Information Model* for C-FIND, C-GET and
          C-MOVE
    identifier : pydicom.dataset.Dataset
        The Query/Retrieve request's *Identifier* dataset.
    session : sqlalchemy.orm.session.Session
        The session we are using to query the database.

    Returns
    -------
    list of Instance
        The matching database Instances.

    Raises
    ------
    ValueError
        If the `identifier` is invalid.
    """
    if model not in _STUDY_ROOT and model not in _PATIENT_ROOT:
        raise ValueError("Unknown information model '{}'".format(model.name))

    # Remove all optional keys, after this only unique/required will remain
    for elem in identifier:
        kw = elem.keyword
        if kw != 'QueryRetrieveLevel' and kw not in _ATTRIBUTES:
            delattr(identifier, kw)

    if model in _C_GET or model in _C_MOVE:
        # Part 4, C.2.2.1.2: remove required keys from C-GET/C-MOVE
        for kw, value in _ATTRIBUTES.items():
            if value[1] == 'R' and kw in identifier:
                delattr(identifier, kw)

    return _search_qr(model, identifier, session)


def _search_qr(model, identifier, session):
    """Search the database using a Query/Retrieve *Identifier* query.

    Parameters
    ----------
    model : pydicom.uid.UID
        Either *Patient Root Query Retrieve Information Model* or *Study Root
        Query Retrieve Information Model* for C-FIND, C-GET or C-MOVE.
    identifier : pydicom.dataset.Dataset
        The request's *Identifier* dataset.
    session : sqlalchemy.orm.session.Session
        The session we are using to query the database.

    Returns
    -------
    list of db.Instance
        The Instances that match the query.
    """
    # Will raise InvalidIdentifier if check failed
    _check_identifier(identifier, model)

    if model in _PATIENT_ROOT:
        attr = _PATIENT_ROOT[model]
    else:
        attr = _STUDY_ROOT[model]

    # Hierarchical search method: C.4.1.3.1.1
    query = None
    for level, keywords in attr.items():
        # Keywords at current level that are in the identifier
        keywords = [kw for kw in keywords if kw in identifier]
        # Create query dataset for only the current level and run it
        ds = Dataset()
        [setattr(ds, kw, getattr(identifier, kw)) for kw in keywords]
        query = build_query(ds, session, query)

        if level == identifier.QueryRetrieveLevel:
            break

    return query.all()


def _search_range(elem, session, query=None):
    """Perform a range search for DA, DT and TM elements with '-' in them.

    Parameters
    ----------
    elem : pydicom.dataelem.DataElement
        The attribute to perform the search with.
    session : sqlalchemy.orm.session.Session
        The session we are using to query the database.
    query : sqlalchemy.orm.query.Query, optional
        An existing query within which this search should be performed. If
        not used then all the Instances in the database will be searched
        (default).

    Returns
    -------
    sqlalchemy.orm.query.Query
        The resulting query.
    """
    # range matching
    #   <date1> - <date2>: matches any date within the range, inclusive
    #   - <date2>: match all dates prior to and including <date2>
    #   <date1> -: match all dates after and including <date1>
    #   <time>: if Timezone Offset From UTC included, values are in specified
    #   date: 20060705-20060707 + time: 1000-1800 matches July 5, 10 am to
    #       July 7, 6 pm.
    start, end = elem.value.split('-')
    attr = getattr(Instance, _TRANSLATION[elem.keyword])
    if not query:
        query = session.query(Instance)

    if start and end:
        return query.filter(attr >= start, attr <= end)
    elif start and not end:
        return query.filter(attr >= start)
    elif not start and end:
        return query.filter(attr <= end)

    raise ValueError("Invalid attribute value for range matching")


def _search_single_value(elem, session, query=None):
    """Perform a search using single value matching.

    Single value matching shall be performed if the value of an Attribute is
    non-zero length and the VR is not SQ and:

    * the VR is AE, CS, LO, LT, PN, SH, ST, UC, UR or UT and contains no wild
      card characters, or
    * the VR is DA, TM or DT and contains a single value with no "-", or
    * any other VR

    Parameters
    ----------
    elem : pydicom.dataelem.DataElement
        The attribute to perform the search with.
    session : sqlalchemy.orm.session.Session
        The session we are using to query the database.
    query : sqlalchemy.orm.query.Query, optional
        An existing query within which this search should be performed. If
        not used then all the Instances in the database will be searched
        (default).

    Returns
    -------
    sqlalchemy.orm.query.Query
        The resulting query.
    """
    attr = getattr(Instance, _TRANSLATION[elem.keyword])
    if elem.VR == 'PN':
        value = str(elem.value)
    else:
        value = elem.value

    if not query:
        query = session.query(Instance)

    return query.filter(attr == value)


def _search_uid_list(elem, session, query=None):
    """Search using an element containing a list of UIDs.

    A match against any of the UIDs is considered a positive result.

    Parameters
    ----------
    elem : pydicom.dataelem.DataElement
        The attribute to perform the search with.
    session : sqlalchemy.orm.session.Session
        The session we are using to query the database.
    query : sqlalchemy.orm.query.Query, optional
        An existing query within which this search should be performed. If
        not used then all the Instances in the database will be searched
        (default).

    Returns
    -------
    sqlalchemy.orm.query.Query
        The resulting query.
    """
    if not elem.value:
        return _search_universal(elem, session, query)

    attr = getattr(Instance, _TRANSLATION[elem.keyword])
    if not query:
        query = session.query(Instance)

    return query.filter(attr.in_(elem.value))


def _search_universal(elem, session, query=None):
    """Perform a universal search for empty elements.

    Parameters
    ----------
    elem : pydicom.dataelem.DataElement
        The attribute to perform the search with.
    session : sqlalchemy.orm.session.Session
        The session we are using to query the database.
    query : sqlalchemy.orm.query.Query, optional
        An existing query within which this search should be performed. If
        not used then all the Instances in the database will be searched
        (default).

    Returns
    -------
    sqlalchemy.orm.query.Query
        The resulting query.
    """
    # If the value is zero length then all entities shall match
    if not query:
        query = session.query(Instance)

    return query


def _search_wildcard(elem, session, query=None):
    """Perform a wildcard search.

    Parameters
    ----------
    elem : pydicom.dataelem.DataElement
        The attribute to perform the search with.
    session : sqlalchemy.orm.session.Session
        The session we are using to query the database.
    query : sqlalchemy.orm.query.Query, optional
        An existing query within which this search should be performed. If
        not used then all the Instances in the database will be searched
        (default).

    Returns
    -------
    sqlalchemy.orm.query.Query
        The resulting query.
    """
    # Contains '*' or '?', case-sensitive if not PN
    #   '*' shall match any sequence of characters (incl. zero length)
    #   '?' shall match any single character
    attr = getattr(Instance, _TRANSLATION[elem.keyword])
    if elem.VR == 'PN':
        value = str(elem.value)
    else:
        value = elem.value

    if value is None or value == '':
        value = '*'

    value = value.replace('*', '%')
    value = value.replace('?', '_')

    if not query:
        query = session.query(Instance)

    return query.filter(attr.like(value))


# Database table setup stuff
Base = declarative_base()


class Image(Base):
    __tablename__ = 'image'
    # (0008,0018) SOP Instance UID | VR UI, VM 1, U
    sop_instance_uid = Column(String(64), primary_key=True)
    # (0020,0013) Instance Number | VR IS, VM 1, R
    instance_number = Column(Integer)


class Instance(Base):
    __tablename__ = 'instance'

    # Absolute path to the stored SOP Instance
    filename = Column(String)
    # Transfer Syntax UID of the SOP Instance
    transfer_syntax_uid = Column(String(64))
    sop_class_uid = Column(String(64))

    patient_id = Column(String, ForeignKey('patient.patient_id'))
    patient_name = Column(String, ForeignKey('patient.patient_id'))

    study_instance_uid = Column(String, ForeignKey('study.study_instance_uid'))
    study_date = Column(String, ForeignKey('study.study_date'))
    study_time = Column(String, ForeignKey('study.study_time'))
    accession_number = Column(String, ForeignKey('study.accession_number'))
    study_id = Column(String, ForeignKey('study.study_id'))

    series_instance_uid = Column(
        String, ForeignKey('series.series_instance_uid')
    )
    modality = Column(String, ForeignKey('series.modality'))
    series_number = Column(String, ForeignKey('series.series_number'))

    sop_instance_uid = Column(
        String, ForeignKey('image.sop_instance_uid'), primary_key=True,
    )
    instance_number = Column(String, ForeignKey('image.instance_number'))

    def as_identifier(self, identifier, model):
        """Return an Identifier dataset matching the elements from a query.

        Parameters
        ----------
        identifier : pydicom.dataset.Dataset
            The C-FIND, C-GET or C-MOVE request's *Identifier* dataset.
        model : pydicom.uid.UID
            The Query/Retrieve Information Model.

        Returns
        -------
        pydicom.dataset.Dataset
            The response *Identifier*.
        """
        ds = Dataset()
        ds.QueryRetrieveLevel = identifier.QueryRetrieveLevel

        if model in _PATIENT_ROOT:
            attr = _PATIENT_ROOT[model]
        else:
            attr = _STUDY_ROOT[model]

        all_keywords = []
        for level, keywords in attr.items():
            all_keywords.extend(keywords)
            if level == identifier.QueryRetrieveLevel:
                break

        for kw in [kw for kw in all_keywords if kw in identifier]:
            try:
                attribute = _TRANSLATION[kw]
            except KeyError:
                continue

            setattr(ds, kw, getattr(self, attribute, None))

        return ds

    @property
    def context(self):
        """Return a presentation context for the Instance.

        Returns
        -------
        pynetdicom.presentation.PresentationContext

        Raises
        ------
        ValueError
            If either of the *SOP Class UID* or *Transfer Syntax UID* is not
            available for the Instance.
        """
        if None in [self.sop_class_uid, self.transfer_syntax_uid]:
            raise ValueError(
                "Cannot determine which presentation context is required for "
                "for the SOP Instance"
            )

        return build_context(self.sop_class_uid, self.transfer_syntax_uid)


class Patient(Base):
    __tablename__ = 'patient'
    # (0010,0020) Patient ID | VR LO, VM 1, U
    patient_id = Column(String(16), primary_key=True)
    # (0010,0010) Patient's Name | VR PN, VM 1, R
    patient_name = Column(String(64))


class Series(Base):
    __tablename__ = 'series'
    # (0020,000E) Series Instance UID | VR UI, VM 1, U
    series_instance_uid = Column(String(64), primary_key=True)
    # (0008,0060) Modality | VR CS, VM 1, R
    modality = Column(String(16))
    # (0020,0011) Series Number | VR IS, VM 1, R
    series_number = Column(Integer)


class Study(Base):
    __tablename__ = 'study'
    # (0020,000D) Study Instance UID | VR UI, VM 1, U
    study_instance_uid = Column(String(64), primary_key=True)
    # (0008,0020) Study Date | VR DA, VM 1, R
    study_date = Column(String(8))
    # (0008,0030) Study Time | VR TM, VM 1, R
    study_time = Column(String(14))
    # (0008,0050) Accession Number | VR SH, VM 1, R
    accession_number = Column(String(16))
    # (0020,0010) Study ID | VR SH, VM 1, R
    study_id = Column(String(16))
