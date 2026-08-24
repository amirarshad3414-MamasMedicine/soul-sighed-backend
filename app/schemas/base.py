"""Shared response conventions.

Every response schema inherits from `XanoSchema` so the wire format matches the
old backend exactly. The rules come from xano-export/formats.md, which was
derived from live rows rather than from the OpenAPI spec:

  * timestamps go out as epoch milliseconds (`1787561676634`), not ISO strings
  * dates go out as "YYYY-MM-DD" — a different format, in the same row
  * null keys are always present; Xano never omits a field, so nothing here may
    use exclude_none or exclude_unset
  * uuids are plain strings
"""
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer


def to_epoch_millis(value: datetime | None) -> int | None:
    return None if value is None else int(value.timestamp() * 1000)


EpochMillis = Annotated[
    datetime | None,
    PlainSerializer(to_epoch_millis, return_type=int | None, when_used="always"),
]


class XanoSchema(BaseModel):
    """Base for responses that mirror a Xano table row."""

    model_config = ConfigDict(from_attributes=True)
