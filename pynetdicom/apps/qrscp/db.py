try:
    import sqlalchemy
except ImportError:
    sys.exit("qrscp.py requires the sqlalchemy package")

from sqlalchemy import (
    create_engine, Column, ForeignKey, Integer, String
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

import config


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
        ('patient_id', 'PatientID', 16),
        ('patient_name', 'PatientName', 64),
        ('study_instance_uid', 'StudyInstanceUID', 64),
        ('study_date', 'StudyDate', 8),
        ('study_time', 'StudyTime', 14),
        ('accession_number', 'AccessionNumber', 16),
        ('study_id', 'StudyID', 16),
        ('series_instance_uid', 'SeriesInstanceUID', 64),
        ('modality', 'Modality', 16),
        ('series_number', 'SeriesNumber', None),
        ('sop_instance_uid', 'SOPInstanceUID', 64),
        ('instance_number', 'InstanceNumber', None),
    ]
    instance = Instance()
    for attr, keyword, max_len in required:
        value = getattr(ds, keyword)

        if max_len:
            assert len(value) < max_len
        else:
            assert -2**31 <= value <= 2**31 - 1

        setattr(instance, attr, getattr(ds, keyword))

    session = session_builder()
    session.add(instance)
    session.commit()


def new(engine):
    """Create a new database."""
    Base.metadata.create_all(engine)


def clear():
    """Delete all entries from the database."""
    pass


def connect():
    """Return a connection to the database.

    Returns
    -------
    sqlalchemy.engine.Connection
        The connection to the database.
    sqlalchemy.orm.Session
        The Session configured with the engine.
    """
    engine = create_engine('sqlite:///.{}'.format(config.DATABASE_LOCATION))

    Session = sessionmaker()
    Session.configure(bind=engine)

    return engine.connect(), Session


def remove_instance(instance_uid, session_builder):
    """Return a SOP Instance from the database.

    Parameters
    ----------
    instance_uid : pydicom.uid.UID
        The () *SOP Instance UID* of the SOP Instance to be removed from the
        database.
    """
    session = session_builder()
    matches = session.query.filter(Instance.sop_instance_uid == instance_uid)
    if matches:
        session.delete(matches[0])


def search(query):
    """Search the database.

    """
    pass


Base = declarative_base()


class Image(Base):
    __tablename__ = 'instance'
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

    patient = relationship(Patient, cascade="add, delete, delete-orphan")
    patient_id = Column(String, ForeignKey('patient.patient_id'))
    patient_name = Column(String, ForeignKey('patient.patient_name'))

    study = relationship(Study, cascade="add, delete, delete-orphan")
    study_instance_uid = Column(String, ForeignKey('study.study_instance_uid'))
    study_date = Column(String, ForeignKey('study.study_date'))
    study_time = Column(String, ForeignKey('study.study_time'))
    accession_number = Column(String, ForeignKey('study.accession_number'))
    study_id = Column(String, ForeignKey('study.study_id'))

    series = relationship(Series, cascade="add, delete, delete-orphan")
    series_instance_uid = Column(
        String, ForeignKey('series.series_instance_uid')
    )
    modality = Column(String, ForeignKey('series.modality'))
    series_number = Column(String, ForeignKey('series.series_number'))

    image = relationship(Image, cascade="add, delete, delete-orphan")
    sop_instance_uid = Column(
        String, ForeignKey('image.sop_instance_uid'), primary_key=True
    )
    instance_number = Column(String, ForeignKey('image.instance_number'))
