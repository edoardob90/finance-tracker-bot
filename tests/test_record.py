import pytest
from models import Record, RecordSchema


def test_empty_record():
    record = Record()

    assert record.date is None
    assert record.amount is None
    assert record.currency is None
    assert record.description is None
    assert record.account is None
    assert record.recorded_at is None


def test_schema_dump():
    schema = RecordSchema()

    assert isinstance(schema.dump({}), dict)


def test_schema_load():
    schema = RecordSchema()
    record = schema.load({})

    assert isinstance(record, Record)
    assert all(
        getattr(record, attr) is None
        for attr in (
            "date",
            "amount",
            "currency",
            "description",
            "account",
            "recorded_at",
        )
    )
