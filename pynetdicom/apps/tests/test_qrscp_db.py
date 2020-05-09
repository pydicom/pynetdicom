"""Unit tests for the QRSCP app's database functions."""

import os

import pytest
import pyfakefs
from sqlalchemy.schema import MetaData
from sqlalchemy.exc import IntegrityError

from pydicom import dcmread
import pydicom.config
from pydicom.dataset import Dataset
from pydicom.tag import Tag

from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelFind

from pynetdicom.apps.qrscp import db
import pynetdicom.apps.qrscp.config as config


TEST_DIR = os.path.dirname(__file__)
TEST_DB = os.path.join(TEST_DIR, 'instances.sqlite')
DATA_DIR = os.path.join(TEST_DIR, '../', '../', 'tests', 'dicom_files')
DATASETS = {
    'CTImageStorage.dcm' : {
        'patient_id' : '1CT1',
        'patient_name' : 'CompressedSamples^CT1',
        'study_instance_uid' : '1.3.6.1.4.1.5962.1.2.1.20040119072730.12322',
        'study_date' : '20040119',
        'study_time' : '072730',
        'accession_number' : None,
        'study_id' : '1CT1',
        'series_instance_uid' : '1.3.6.1.4.1.5962.1.3.1.1.20040119072730.12322',
        'modality' : 'CT',
        'series_number' : '1',
        'sop_instance_uid' : '1.3.6.1.4.1.5962.1.1.1.1.1.20040119072730.12322',
        'instance_number' : '1',
        'transfer_syntax_uid' : '1.2.840.10008.1.2.1',
        'sop_class_uid' : '1.2.840.10008.5.1.4.1.1.2',
    },
    'MRImageStorage_ExplicitVRBigEndian.dcm' : {
        'patient_id' : '4MR1',
        'patient_name' : 'CompressedSamples^MR1',
        'study_instance_uid' : '1.3.6.1.4.1.5962.1.2.4.20040826185059.5457',
        'study_date' : '20040826',
        'study_time' : '185059',
        'accession_number' : None,
        'study_id' : '4MR1',
        'series_instance_uid' : '1.3.6.1.4.1.5962.1.3.4.1.20040826185059.5457',
        'modality' : 'MR',
        'series_number' : '1',
        'sop_instance_uid' : '1.3.6.1.4.1.5962.1.1.4.1.1.20040826185059.5457.1',
        'instance_number' : '1',
        'transfer_syntax_uid' : '1.2.840.10008.1.2.4.90',
        'sop_class_uid' : '1.2.840.10008.5.1.4.1.1.4',
    },
    'MRImageStorage_JPG2000_Lossless.dcm' : {
        'patient_id' : '4MR1',
        'patient_name' : 'CompressedSamples^MR1',
        'study_instance_uid' : '1.3.6.1.4.1.5962.1.2.4.20040826185059.5457',
        'study_date' : '20040826',
        'study_time' : '185059',
        'accession_number' : None,
        'study_id' : '4MR1',
        'series_instance_uid' : '1.3.6.1.4.1.5962.1.3.4.1.20040826185059.5457',
        'modality' : 'MR',
        'series_number' : '1',
        'sop_instance_uid' : '1.3.6.1.4.1.5962.1.1.4.1.1.20040826185059.5457',
        'instance_number' : '1',
        'transfer_syntax_uid' : '1.2.840.10008.1.2.4.90',
        'sop_class_uid' : '1.2.840.10008.5.1.4.1.1.4',
    },
    'RTImageStorage.dcm' : {
        'patient_id' : '0123456789',
        'patient_name' : 'ANON^A^B^C^D',
        'study_instance_uid' : '1.3.46.423632.132218.1415242681.6',
        'study_date' : '20150803',
        'study_time' : '114426',
        'accession_number' : None,
        'study_id' : '00000000',
        'series_instance_uid' : '1.3.46.423632.132218.1415243125.23',
        'modality' : 'RTIMAGE',
        'series_number' : '000000052637',
        'sop_instance_uid' : '1.3.46.423632.132218.1438566266.11',
        'instance_number' : '000000056675',
        'transfer_syntax_uid' : '1.2.840.10008.1.2',
        'sop_class_uid' : '1.2.840.10008.5.1.4.1.1.481.1',
    },
    'SCImageStorage_Deflated.dcm' : {
        'patient_id' : None,
        'patient_name' : '^^^^',
        'study_instance_uid' : '1.3.6.1.4.1.5962.1.2.0.977067310.6001.0',
        'study_date' : None,
        'study_time' : None,
        'accession_number' : None,
        'study_id' : None,
        'series_instance_uid' : '1.3.6.1.4.1.5962.1.3.0.0.977067310.6001.0',
        'modality' : 'OT',
        'series_number' : None,
        'sop_instance_uid' : '1.3.6.1.4.1.5962.1.1.0.0.0.977067309.6001.0',
        'instance_number' : None,
        'transfer_syntax_uid' : '1.2.840.10008.1.2.1.99',
        'sop_class_uid' : '1.2.840.10008.5.1.4.1.1.7',
    },
}


class TestConnect(object):
    """Tests for db.connect()."""
    def setup(self):
        """Run prior to each test"""
        self.orig = config.DATABASE_LOCATION
        config.DATABASE_LOCATION = TEST_DB

    def teardown(self):
        """Clear any active threads"""
        config.DATABASE_LOCATION = self.orig

    def test_create_new(self):
        """Test connecting to the instance database if it doesn't exist."""
        assert not os.path.exists(config.DATABASE_LOCATION)
        conn, engine, session = db.connect()
        assert os.path.exists(config.DATABASE_LOCATION)

        # Check exists with tables
        meta = MetaData(bind=engine)
        meta.reflect(bind=engine)
        assert 'patient' in meta.tables
        assert 'study' in meta.tables
        assert 'series' in meta.tables
        assert 'image' in meta.tables
        assert 'instance' in meta.tables

        os.remove(config.DATABASE_LOCATION)
        assert not os.path.exists(config.DATABASE_LOCATION)

    def test_create_new_existing(self):
        """Test connecting to the instance database if it exists."""
        conn, engine, session = db.connect()
        assert os.path.exists(config.DATABASE_LOCATION)

        conn, engine, session = db.connect()

        meta = MetaData(bind=engine)
        meta.reflect(bind=engine)
        assert 'patient' in meta.tables
        assert 'study' in meta.tables
        assert 'series' in meta.tables
        assert 'image' in meta.tables
        assert 'instance' in meta.tables

        os.remove(config.DATABASE_LOCATION)
        assert not os.path.exists(config.DATABASE_LOCATION)


class TestAddInstance(object):
    """Tests for db.add_instance()."""
    def setup(self):
        """Run prior to each test"""
        self.conn, self.engine, self.session = db.connect('sqlite:///:memory:')
        pydicom.config.use_none_as_empty_text_VR_value = True

        ds = Dataset()
        ds.PatientID = '1234'
        ds.StudyInstanceUID = '1.2'
        ds.SeriesInstanceUID = '1.2.3'
        ds.SOPInstanceUID = '1.2.3.4'
        self.minimal = ds

    def test_add_instance(self):
        """Test adding to the instance database."""
        fpath = os.path.join(DATA_DIR, 'CTImageStorage.dcm')
        ds = dcmread(fpath)
        db.add_instance(ds, self.session)

        session = self.session()
        obj = session.query(db.Instance).all()
        assert 1 == len(obj)
        for kk, vv in DATASETS['CTImageStorage.dcm'].items():
            assert vv == getattr(obj[0], kk)

    def test_add_multiple_instances(self):
        """Test adding multiple data to the instance database."""
        for fname in DATASETS:
            fpath = os.path.join(DATA_DIR, fname)
            ds = dcmread(fpath)
            db.add_instance(ds, self.session)

        session = self.session()
        obj = session.query(db.Instance).all()
        assert 5 == len(obj)
        obj = session.query(db.Instance, db.Instance.patient_name).all()
        names = [val[1] for val in obj]
        assert 'CompressedSamples^CT1' in names
        assert 'CompressedSamples^MR1' in names
        assert 'ANON^A^B^C^D' in names
        assert '^^^^' in names

    def test_add_minimal(self):
        """Test adding a minimal dataset."""
        db.add_instance(self.minimal, self.session)
        session = self.session()
        obj = session.query(db.Instance).all()
        assert 1 == len(obj)
        assert '1234' == obj[0].patient_id
        assert '1.2' == obj[0].study_instance_uid
        assert '1.2.3' == obj[0].series_instance_uid
        assert '1.2.3.4' == obj[0].sop_instance_uid

        rest = [
            'patient_name', 'study_date', 'study_time', 'accession_number',
            'study_id', 'modality', 'series_number', 'instance_number',
        ]
        for attr in rest:
            assert getattr(obj[0], attr) is None

    def test_bad_instance(self):
        """Test that instances with bad data aren't added."""
        keywords = [
            ('PatientID', 16),
            ('PatientName', 64),
            ('StudyInstanceUID', 64),
            ('StudyDate', 8),
            ('StudyTime', 14),
            ('AccessionNumber', 16),
            ('StudyID', 16),
            ('SeriesInstanceUID', 64),
            ('Modality', 16),
            #('SeriesNumber', None),
            ('SOPInstanceUID', 64),
            #('InstanceNumber', None),
        ]
        ds = self.minimal[:]
        for kw, max_len in keywords:
            setattr(ds, kw, 'a' * (max_len + 1))
            with pytest.raises(AssertionError):
                db.add_instance(ds, self.session)

        session = self.session()
        assert not session.query(db.Instance).all()

    def test_bad_instance_none(self):
        """Test that instances with bad data aren't added."""
        keywords = [
            ('PatientID', 16),
            ('PatientName', 64),
            ('StudyInstanceUID', 64),
            ('StudyDate', 8),
            ('StudyTime', 14),
            ('AccessionNumber', 16),
            ('StudyID', 16),
            ('SeriesInstanceUID', 64),
            ('Modality', 16),
            #('SeriesNumber', None),
            ('SOPInstanceUID', 64),
            #('InstanceNumber', None),
        ]
        ds = Dataset()
        ds.PatientID = None
        ds.StudyInstanceUID = None
        ds.SeriesInstanceUID = None
        ds.SOPInstanceUID = None
        with pytest.raises(IntegrityError):
            db.add_instance(ds, self.session)

        session = self.session()
        assert not session.query(db.Instance).all()

    def test_instance_exists(self):
        """Test that adding already existing instance updates it."""
        db.add_instance(self.minimal, self.session)

        session = self.session()
        result = session.query(db.Instance).all()
        assert 1 == len(result)
        assert None == result[0].modality

        self.minimal.Modality = 'CT'

        session = self.session()
        db.add_instance(self.minimal, self.session)
        result = session.query(db.Instance).all()
        assert 1 == len(result)
        assert 'CT' == result[0].modality


class TestRemoveInstance(object):
    """Tests for db.remove_instance()."""
    def setup(self):
        """Run prior to each test"""
        self.orig = config.DATABASE_LOCATION
        config.DATABASE_LOCATION = TEST_DB

        self.conn, self.engine, self.session = db.connect('sqlite:///:memory:')
        pydicom.config.use_none_as_empty_text_VR_value = True

        ds = Dataset()
        ds.PatientID = '1234'
        ds.StudyInstanceUID = '1.2'
        ds.SeriesInstanceUID = '1.2.3'
        ds.SOPInstanceUID = '1.2.3.4'
        db.add_instance(ds, self.session)

        self.minimal = ds

    def test_remove_existing(self):
        """Test removing if exists in database."""
        session = self.session()
        obj = session.query(db.Instance).all()
        assert 1 == len(obj)
        assert '1.2.3.4' == obj[0].sop_instance_uid

        db.remove_instance('1.2.3.4', self.session)
        session = self.session()
        assert not session.query(db.Instance).all()
        assert not session.query(db.Patient).all()
        assert not session.query(db.Study).all()
        assert not session.query(db.Series).all()
        assert not session.query(db.Image).all()

    def test_remove_not_existing(self):
        """Test removing if doesn't exist in database."""
        session = self.session()
        obj = session.query(db.Instance).all()
        assert 1 == len(obj)
        assert '1.2.3.4' == obj[0].sop_instance_uid

        db.remove_instance('1.2.3.5', self.session)
        session = self.session()
        assert session.query(db.Instance).all()


class TestClear(object):
    """Tests for db.clear()."""
    def setup(self):
        """Run prior to each test"""
        self.conn, self.engine, self.session = db.connect('sqlite:///:memory:')
        pydicom.config.use_none_as_empty_text_VR_value = True

        for fname in DATASETS:
            fpath = os.path.join(DATA_DIR, fname)
            ds = dcmread(fpath)
            db.add_instance(ds, self.session)

    def test_clear(self):
        """Test removing if exists in database."""
        session = self.session()
        assert 5 == len(session.query(db.Instance).all())

        db.clear(self.session)
        assert not session.query(db.Instance).all()


class TestSearch(object):
    """Tests for db.search()."""
    def setup(self):
        """Run prior to each test"""
        self.conn, self.engine, self.session = db.connect('sqlite:///:memory:')
        pydicom.config.use_none_as_empty_text_VR_value = True

        for fname in DATASETS:
            fpath = os.path.join(DATA_DIR, fname)
            ds = dcmread(fpath)
            db.add_instance(ds, self.session)

    def test_search(self):
        """Test simple search."""
        pass

    def test_search_range_both(self):
        """Test searching a range with both start and end."""
        query = Dataset()
        query.QueryRetrieveLevel = 'PATIENT'
        query.StudyDate = '20000101-20200101'
        q = db._search_range(query['StudyDate'], self.session)
        assert 4 == len(q.all())

        query.StudyDate = '20000101-20150101'
        q = db._search_range(query['StudyDate'], self.session)
        assert 3 == len(q.all())

        query.StudyDate = '20000101-20010101'
        q = db._search_range(query['StudyDate'], self.session)
        assert not q.all()

    def test_search_range_start(self):
        """Test searching a range with only start."""
        query = Dataset()
        query.QueryRetrieveLevel = 'PATIENT'
        query.StudyDate = '20000101-'
        q = db._search_range(query['StudyDate'], self.session)
        assert 4 == len(q.all())

        query.StudyDate = '20150101-'
        q = db._search_range(query['StudyDate'], self.session)
        assert 1 == len(q.all())

        query.StudyDate = '20200101-'
        q = db._search_range(query['StudyDate'], self.session)
        assert not q.all()

    def test_search_range_end(self):
        """Test searching a range with only end."""
        query = Dataset()
        query.QueryRetrieveLevel = 'PATIENT'
        query.StudyDate = '-20200101'
        q = db._search_range(query['StudyDate'], self.session)
        assert 4 == len(q.all())

        query.StudyDate = '-20150101'
        q = db._search_range(query['StudyDate'], self.session)
        assert 3 == len(q.all())

        query.StudyDate = '-20010101'
        q = db._search_range(query['StudyDate'], self.session)
        assert not q.all()

    def test_search_range_neither(self):
        """Test searching a range with only end."""
        query = Dataset()
        query.QueryRetrieveLevel = 'PATIENT'
        query.StudyDate = '-'
        with pytest.raises(ValueError):
            db._search_range(query['StudyDate'], self.session)

    def test_search_single_value(self):
        """Test search using a single value."""
        query = Dataset()
        query.QueryRetrieveLevel = 'PATIENT'
        query.PatientName = 'CompressedSamples^CT1'
        q = db._search_single_value(query['PatientName'], self.session)
        assert 1 == len(q.all())

    def test_search_wildcard_asterisk(self):
        """Test search using a * wildcard."""
        query = Dataset()
        query.QueryRetrieveLevel = 'PATIENT'

        query.PatientName = '*'
        q = db._search_wildcard(query['PatientName'], self.session)
        assert 5 == len(q.all())

        query.PatientName = 'CompressedSamples*'
        q = db._search_wildcard(query['PatientName'], self.session)
        assert 3 == len(q.all())

    def test_search_wildcard_qmark(self):
        """Test search using a ? wildcard."""
        query = Dataset()
        query.QueryRetrieveLevel = 'PATIENT'

        query.PatientName = 'CompressedSamples^??1'
        q = db._search_wildcard(query['PatientName'], self.session)
        assert 3 == len(q.all())

    def test_search_uid_list(self):
        """Test search using a UID list."""
        query = Dataset()
        query.QueryRetrieveLevel = 'PATIENT'

        query.SOPInstanceUID = []
        q = db._search_uid_list(query['SOPInstanceUID'], self.session)
        assert 0 == len(q.all())

        query.SOPInstanceUID = [
            '1.3.6.1.4.1.5962.1.1.4.1.1.20040826185059.5457'
        ]
        q = db._search_uid_list(query['SOPInstanceUID'], self.session)
        assert 1 == len(q.all())

        query.SOPInstanceUID = [
            '1.3.6.1.4.1.5962.1.1.4.1.1.20040826185059.5457',
            '1.3.6.1.4.1.5962.1.1.1.1.1.20040119072730.12322'
        ]
        q = db._search_uid_list(query['SOPInstanceUID'], self.session)
        assert 2 == len(q.all())

        query.SOPInstanceUID = [
            '1.3.6.1.4.1.5962.1.1.4.1.1.20040826185059.5457',
            '1.3.6.1.4.1.5962.1.1.1.1.1.20040119072730.12322',
            '1.3.46.423632.132218.1415242681.6'
        ]
        q = db._search_uid_list(query['SOPInstanceUID'], self.session)
        assert 2 == len(q.all())

    def test_combine_queries(self):
        """Test combining queries."""
        query = Dataset()
        query.QueryRetrieveLevel = 'PATIENT'
        query.PatientName = 'CompressedSamples*'
        query.StudyDate = '20000101-20040119'

        q1 = db._search_wildcard(query['PatientName'], self.session)
        q2 = db._search_range(query['StudyDate'], self.session)
        q = q1.intersect(q2)
        assert 1 == len(q.all())


class TestSearchFind(object):
    """Tests for running C-FIND queries against the database."""
    def setup(self):
        """Run prior to each test"""
        self.conn, self.engine, self.session = db.connect('sqlite:///:memory:')
        pydicom.config.use_none_as_empty_text_VR_value = True

        for fname in DATASETS:
            fpath = os.path.join(DATA_DIR, fname)
            ds = dcmread(fpath)
            db.add_instance(ds, self.session)

    def test_patient_minimal(self):
        """Test query at PATIENT level for Patient Root."""
        query = Dataset()
        query.QueryRetrieveLevel = 'PATIENT'
        query.PatientID = None

        result = db.search(
            PatientRootQueryRetrieveInformationModelFind,
            query,
            self.session
        )
        for instance in result:
            print(instance.as_identifier(query))
