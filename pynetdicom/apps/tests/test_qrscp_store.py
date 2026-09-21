"""Unit tests for the QRSCP app's C-STORE handler."""

import logging
from datetime import datetime

import pytest

try:
    import sqlalchemy  # noqa: F401

    HAVE_SQLALCHEMY = True
except ImportError:
    HAVE_SQLALCHEMY = False

from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian


class DummyRequestor:
    address = "127.0.0.1"
    port = 11112


class DummyAssoc:
    requestor = DummyRequestor()


class DummyEvent:
    assoc = DummyAssoc()

    def __init__(self, ds, file_meta):
        self.dataset = ds
        self.file_meta = file_meta
        self.timestamp = datetime.now()


@pytest.mark.skipif(not HAVE_SQLALCHEMY, reason="Requires sqlalchemy")
def test_handle_store_sanitises_sop_instance_uid(tmp_path):
    """A UID with path separators must not escape the storage directory."""
    from pynetdicom.apps.qrscp.db import create
    from pynetdicom.apps.qrscp.handlers import handle_store

    # Nested so an escaping write lands inside tmp_path but outside storage_dir
    storage_dir = tmp_path / "a" / "b" / "storage"
    storage_dir.mkdir(parents=True)
    db_path = f"sqlite:///{tmp_path / 'db.sqlite'}"
    create(db_path)

    ds = Dataset()
    ds.PatientID = "1234"
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = "../../escaped"
    file_meta = FileMetaDataset()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.MediaStorageSOPClassUID = CTImageStorage
    file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID

    handle_store(
        DummyEvent(ds, file_meta), str(storage_dir), db_path, None, logging.getLogger()
    )

    written = list(storage_dir.iterdir())
    assert not (tmp_path / "a" / "escaped").exists()
    assert len(written) == 1
    assert written[0].parent == storage_dir
