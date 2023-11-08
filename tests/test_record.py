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


def test_schema_dump_empty():
    schema = RecordSchema()

    assert isinstance(schema.dump({}), dict)


def test_schema_load_empty():
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


def test_schema_many_empty():
    schema = RecordSchema()
    records = schema.load([{}, {}], many=True)

    assert isinstance(records, list)
    assert all(isinstance(record, Record) for record in records)
    assert all(
        all(
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
        for record in records
    )
