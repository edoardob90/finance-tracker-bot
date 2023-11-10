import pytest
from models import Amount, Record
from pydantic import ValidationError


@pytest.fixture
def amount():
    return Amount(value="100", currency="EUR")


def test_empty_amount():
    with pytest.raises(ValidationError):
        Amount()  # type: ignore


def test_unknown_currency():
    with pytest.raises(ValidationError):
        Amount(value="100", currency="XYZ")


@pytest.fixture
def record():
    return Record()


def test_empty_record(record: Record):
    assert record.date is None
    assert record.amount is None
    assert record.description is None
    assert record.account is None
    assert record.recorded_at is None


def test_schema_dump_empty(record: Record):
    assert isinstance(record.model_dump(), dict)


def test_schema_many_empty(record: Record):
    records = [record for _ in range(3)]

    assert isinstance(records, list)
    assert all(isinstance(record, Record) for record in records)
    assert all(
        all(
            getattr(record, attr) is None
            for attr in (
                "date",
                "amount",
                "description",
                "account",
                "recorded_at",
            )
        )
        for record in records
    )
