try:
    import sqlalchemy
except ImportError:
    sys.exit("qrscp.py requires the sqlalchemy package")

from sqlalchemy import (
    create_engine, Column, ForeignKey, Integer, String
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

import pynetdicom.apps.qrscp.config as config


# CS - 16 bytes maximum
# DA - 8 bytes fixed YYYYMMDD
# IS - 12 bytes maximum, range
# LO - 64 characters maximum
# PN - 64 characters maximum per component group (5 components make a group)
# SH - 16 characters maximum
# TM - 14 bytes maximum HHMMSS.FFFFFF
# UI - 64 bytes maximum

TRANSLATION = {
    'PatientID' : 'patient_id',
    'PatientName' : 'patient_name',
    'StudyInstanceUID' : 'study_instance_uid',
    'StudyDate' : 'study_date',
    'StudyTime' : 'study_time',
    'AccessionNumber' : 'accession_number',
    'StudyID' : 'study_id',
    'SeriesInstanceUID' : 'series_instance_uid',
    'Modality' : 'modality',
    'SeriesNumber' : 'series_number',
    'SOPInstanceUID' : 'sop_instance_uid',
    'InstanceNumber' : 'instance_number',
}


def add_instance(ds, session_builder, fpath=None):
    """Add a SOP Instance to the database.

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        The SOP Instance to be added to the database.
    session_builder : sqlalchemy.orm.Session
    fpath : str, optional
        The path to where the SOP Instance is stored, taken relative
        to the database file.
    """
    # Unique or Required attributes
    required = [
        # (Instance() attribute, DICOM keyword)
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
    instance = Instance()

    # Unique and Required attributes
    for attr, keyword, max_len, unique in required:
        if not unique and keyword not in ds:
            value = None
        else:
            elem = ds[keyword]
            value = elem.value

        if value is not None:
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
    except (AttributeError, AssertionError):
        pass

    # SOP Class UID
    try:
        uid = ds.SOPClassUID
        if uid:
            assert len(uid) < 64
            instance.sop_class_uid = uid
    except (AttributeError, AssertionError):
        pass

    session = session_builder()
    session.add(instance)
    session.commit()


def clear(session_builder):
    """Delete all entries from the database.

    Parameters
    ----------
    session_builder
    """
    session = session_builder()
    for instance in session.query(Instance).all():
        session.delete(instance)

    session.commit()


def connect(db_location=None, echo=False):
    """Return a connection to the database.

    Parameters
    ----------
    db_location : str, optional
        The location of the database (default:
        ``sqlite:///config.DATABASE_LOCATION``). Should only be used when
        testing.
    echo : bool, optional
        Turn the sqlalchemy logging on (default ``False``).

    Returns
    -------
    sqlalchemy.engine.Connection
        The connection to the database.
    sqlalchemy.orm.Session
        The Session configured with the engine.
    """
    if not db_location:
        db_location = 'sqlite:///{}'.format(config.DATABASE_LOCATION)

    engine = create_engine(db_location, echo=echo)

    Session = sessionmaker(bind=engine)

    # Create the tables (won't recreate tables already present)
    Base.metadata.create_all(engine)

    conn = engine.connect()

    return conn, engine, Session


def remove_instance(instance_uid, session_builder):
    """Return a SOP Instance from the database.

    Parameters
    ----------
    instance_uid : pydicom.uid.UID
        The () *SOP Instance UID* of the SOP Instance to be removed from the
        database.
    """
    session = session_builder()
    matches = session.query(Instance).filter(
        Instance.sop_instance_uid == instance_uid
    ).all()
    if matches:
        session.delete(matches[0])
        session.commit()


def search(model, query, session_builder):
    """Search the database.

    Parameters
    ----------
    model : pydicom.uid.UID
        The Query/Retrieve Information Model. Supported models are *Patient
        Root* and *Study Root*.
    query : pydicom.dataset.Dataset
        The Query/Retrieve request's *Identifier* dataset.
    session_builder :

    Returns
    -------
    list of str
        The paths to the files matching the query.
    """
    # sequence matching
    #   May be a sequence with 1 item, which contains zero or more attributes
    #   each attribute matched as normal, if all attributes match then success
    # multiple values
    #   if VM > 1, if one value matches then all values returned
    patient_root_models = [
        '1.2.840.10008.5.1.4.1.2.1.1',
        '1.2.840.10008.5.1.4.1.2.1.2',
        '1.2.840.10008.5.1.4.1.2.1.3'
    ]
    study_root_models = [
        '1.2.840.10008.5.1.4.1.2.2.1',
        '1.2.840.10008.5.1.4.1.2.2.2',
        '1.2.840.10008.5.1.4.1.2.2.3',
    ]

    qr_level = query.QueryRetrieveLevel
    if model in patient_root_models:
        if qr_level == 'PATIENT':
            assert 'PatientID' in query
        elif qr_level == 'STUDY':
            assert 'PatientID' in query
            assert 'StudyInstanceUID' in query
        elif qr_level == 'SERIES':
            assert 'PatientID' in query
            assert 'StudyInstanceUID' in query
            assert 'SeriesInstanceUID' in query
        elif qr_level == 'IMAGE':
            assert 'PatientID' in query
            assert 'StudyInstanceUID' in query
            assert 'SeriesInstanceUID' in query
            assert 'SOPInstanceUID' in query
    elif model in study_root_models:
        if qr_level == 'STUDY':
            assert 'StudyInstanceUID' in query
        elif qr_level == 'PATIENT':
            assert 'PatientID' in query
            assert 'StudyInstanceUID' in query
        elif qr_level == 'SERIES':
            assert 'PatientID' in query
            assert 'StudyInstanceUID' in query
            assert 'SeriesInstanceUID' in query
        elif qr_level == 'IMAGE':
            assert 'PatientID' in query
            assert 'StudyInstanceUID' in query
            assert 'SeriesInstanceUID' in query
            assert 'SOPInstanceUID' in query
    else:
        raise ValueError()

    del ds.QueryRetrieveLevel

    matches = []
    for elem in query if elem.keyword in TRANSLATION:
        if elem.VR in ['DT', 'TM'] and '-' in elem.value:
            matches.append(_search_range(elem, session_builder))
        elif elem.VR == 'UI' and elem.VM > 1:
            matches.append(_search_uid_list(elem, session_builder))
        elif elem.VR != 'PN' and '*' in elem.value or '?' in elem.value:
            matches.append(_search_wildcard(elem, session_builder))
        elif elem.VR != 'PN' and elem.value is None or elem.value == '':
            matches.append(_search_wildcard(elem, session_builder))

    return


def _search_single_value(attribute, session_builder):
    """
    """
    # single value matching
    #   VR: AE, CS, LO, LT, PN, SH, ST, UC, UR, UT and no '*' or '?'
    #   VR: DA, TM, DT and a single value with no '-'
    #   VR: all others
    #   non-PN: Case-sensitive, only entities with values that match exactly
    #   PN: May/may not be case-sensitive, accent-sensitive
    session = session_builder()
    attr = getattr(Instance, TRANSLATION[attribute.keyword])
    if attribute.VR == 'PN':
        # PN probably needs its own function
        value = str(attribute.value)
    else:
        value = attribute.value

    return session.query(Instance).filter(attr == value)


def _search_uid_list(attribute, session_builder):
    """
    """
    # list of UID matching
    #   Each UID in the list may generate a match
    session = session_builder()
    attr = getattr(Instance, TRANSLATION[attribute.keyword])

    return session.query(Instance).filter(attr.in_(attribute.value))


def _search_universal():
    # universal matching
    #   If the value is zero length then all entities shall match
    pass


def _search_wildcard(attribute, session_builder):
    """
    '?' or '*' in query attribute
    """
    # wildcard matching
    #   Contains '*' or '?', case-sensitive if not PN
    #   '*' shall match any sequence of characters (incl. zero length)
    #   '?' shall match any single character
    session = session_builder()
    attr = getattr(Instance, TRANSLATION[attribute.keyword])
    if attribute.VR == 'PN':
        value = str(attribute.value)
    else:
        value = attribute.value

    if value is None or value == '':
        value = '*'

    value = value.replace('*', '%')
    value = value.replace('?', '_')

    return session.query(Instance).filter(attr.like(value))


def _search_range(attribute, session_builder):
    """

    Date and Time if '-' in query attribute

    Returns
    -------
    sqlalchemy.orm.Query
        The results of the range search.
    """
    # range matching
    #   <date1> - <date2>: matches any date within the range, inclusive
    #   - <date2>: match all dates prior to and including <date2>
    #   <date1> -: match all dates after and including <date1>
    #   <time>: if Timezone Offset From UTC included, values are in specified
    #   date: 20060705-20060707 + time: 1000-1800 matches July 5, 10 am to
    #       July 7, 6 pm.
    session = session_builder()
    start, end = attribute.value.split('-')
    attr = getattr(Instance, TRANSLATION[attribute.keyword])
    if start and end:
        return session.query(Instance).filter(attr >= start, attr <= end)
    elif start and not end:
        return session.query(Instance).filter(attr >= start)
    elif not start and end:
        return session.query(Instance).filter(attr <= end)

    raise ValueError("Invalid attribute value")


Base = declarative_base()


class Image(Base):
    __tablename__ = 'image'
    # (0008,0018) SOP Instance UID | VR UI, VM 1, U
    sop_instance_uid = Column(String(64), primary_key=True)
    # (0020,0013) Instance Number | VR IS, VM 1, R
    instance_number = Column(Integer)


class Instance(Base):
    __tablename__ = 'instance'

    # Relative path from the DB file to the stored SOP Instance
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


class Patient(Base):
    __tablename__ = 'patient'
    # (0010,0020) Patient ID | VR LO, VM 1, U
    patient_id = Column(String(16), primary_key=True)
    # (0010,0010) Patient's Name | VR PN, VM 1, R
    patient_name = Column(String(64))


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


class Series(Base):
    __tablename__ = 'series'
    # (0020,000E) Series Instance UID | VR UI, VM 1, U
    series_instance_uid = Column(String(64), primary_key=True)
    # (0008,0060) Modality | VR CS, VM 1, R
    modality = Column(String(16))
    # (0020,0011) Series Number | VR IS, VM 1, R
    series_number = Column(Integer)
