# -*- coding: utf-8 -*-
"""Electrical billing for small consumers in Spain using PVPC. Base dataclass."""
import json
from datetime import datetime
from enum import Enum

import attr
import cattr

# Serialization hooks for datetimes and Enums
cattr.register_unstructure_hook(Enum, lambda e: e.value)
cattr.register_structure_hook(Enum, lambda s, enum_cls: enum_cls(s))

time_format = "%Y-%m-%d %H:%M:%S"
cattr.register_unstructure_hook(datetime, lambda dt: dt.strftime(time_format))
cattr.register_structure_hook(datetime, lambda s, _: datetime.strptime(s, time_format))


@attr.s
class Base:
    """
    Base dataclass to store information related to the electric bill.

    * Implements instance methods to serialize the data to dict or JSON
    * And class constructors to
    """

    def to_dict(self):
        """
        Generate dict representation.

        To be stored or shared, so it can be retrieved again with
         `bill = FacturaData.from_dict(data)`
        """
        return cattr.unstructure(self)

    def to_json(self, indent=2, **kwargs) -> str:
        """
        Generate JSON representation.

        To be stored or shared, so it can be retrieved again with
         `bill = FacturaData.from_json(json_data)`
        """
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, **kwargs)

    @classmethod
    def from_dict(cls, raw_data: dict):
        """Constructor from dict representation."""
        return cattr.structure(raw_data, cls)

    @classmethod
    def from_json(cls, raw_data: str):
        """Constructor from JSON representation."""
        return cls.from_dict(json.loads(raw_data))
