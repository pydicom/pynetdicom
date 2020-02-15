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


def add_instance(ds, session_builder):
    """Add a SOP Instance to the database.

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        The SOP Instance to be added to the database.
    session_builder : sqlalchemy.orm.Session
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

    session = session_builder()
    session.add(instance)
    session.commit()


def new(engine):
    """Create a new database."""
    Base.metadata.create_all(engine)


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
        ``sqlite:///config.DATABASE_LOCATION``).
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


def search(query):
    """Search the database.

    """
    # single value matching
    #   VR: AE, CS, LO, LT, PN, SH, ST, UC, UR, UT and no '*' or '?'
    #   VR: DA, TM, DT and a single value with no '-'
    #   VR: all others
    #   non-PN: Case-sensitive, only entities with values that match exactly
    #   PN: May/may not be case-sensitive, accent-sensitive
    # list of UID matching
    #   Each UID in the list may generate a match
    # universal matching
    #   If the value is zero length then all entities shall match
    # wildcard matching
    #   Contains '*' or '?', case-sensitive if not PN
    #   '*' shall match any sequence of characters (incl. zero length)
    #   '?' shall match any single character
    # range matching
    #   <date1> - <date2>: matches any date within the range, inclusive
    #   - <date2>: match all dates prior to and including <date2>
    #   <date1> -: match all dates after and including <date1>
    #   <time>: if Timezone Offset From UTC included, values are in specified
    #   date: 20060705-20060707 + time: 1000-1800 matches July 5, 10 am to
    #       July 7, 6 pm.
    # sequence matching
    #   May be a sequence with 1 item, which contains zero or more attributes
    #   each attribute matched as normal, if all attributes match then success
    # multiple values
    #   if VM > 1, if one value matches then all values returned
    pass


Base = declarative_base()


class Image(Base):
    __tablename__ = 'image'
    # (0008,0018) SOP Instance UID | UI | 1 - U
    sop_instance_uid = Column(String(64), primary_key=True)
    # (0020,0013) Instance Number | IS | 1 - R
    instance_number = Column(Integer)


class Patient(Base):
    __tablename__ = 'patient'
    # (0010,0020) Patient ID | LO | 1 - U
    patient_id = Column(String(16), primary_key=True)
    # (0010,0010) Patient's Name | PN | 1 - R
    patient_name = Column(String(64))


class Study(Base):
    __tablename__ = 'study'
    # (0020,000D) Study Instance UID | UI | 1 - U
    study_instance_uid = Column(String(64), primary_key=True)
    # (0008,0020) Study Date | DA | 1 - R
    study_date = Column(String(8))
    # (0008,0030) Study Time | TM | 1 - R
    study_time = Column(String(14))
    # (0008,0050) Accession Number | SH | 1 - R
    accession_number = Column(String(16))
    # (0020,0010) Study ID | SH | 1 - R
    study_id = Column(String(16))


class Series(Base):
    __tablename__ = 'series'
    # (0020,000E) Series Instance UID | UI | 1 - U
    series_instance_uid = Column(String(64), primary_key=True)
    # (0008,0060) Modality | CS | 1 - R
    modality = Column(String(16))
    # (0020,0011) Series Number | IS | 1 - R
    series_number = Column(Integer)


class Instance(Base):
    __tablename__ = 'instance'

    # Relative path from the DB file to the stored SOP Instance
    filename = Column(String)

    patient_id = Column(String, ForeignKey('patient.patient_id'))
    patient_name = Column(String, ForeignKey('patient.patient_id'))
    #patient = relationship(
    #    Patient,
        #foreign_keys=[patient_id, patient_name],
    #    cascade="all, delete, delete-orphan"
    #)

    #study = relationship(Study, cascade="all, delete, delete-orphan")
    study_instance_uid = Column(String, ForeignKey('study.study_instance_uid'))
    study_date = Column(String, ForeignKey('study.study_date'))
    study_time = Column(String, ForeignKey('study.study_time'))
    accession_number = Column(String, ForeignKey('study.accession_number'))
    study_id = Column(String, ForeignKey('study.study_id'))

    #series = relationship(Series, cascade="all, delete, delete-orphan")
    series_instance_uid = Column(
        String, ForeignKey('series.series_instance_uid')
    )
    modality = Column(String, ForeignKey('series.modality'))
    series_number = Column(String, ForeignKey('series.series_number'))

    #image = relationship(Image, cascade="all, delete, delete-orphan")
    sop_instance_uid = Column(
        String, ForeignKey('image.sop_instance_uid'), primary_key=True
    )
    instance_number = Column(String, ForeignKey('image.instance_number'))
