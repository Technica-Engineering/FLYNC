import logging
from typing import Optional

import pydantic
from pydantic import PrivateAttr  # noqa F401
from pydantic import BaseModel, ConfigDict


class FLYNCBaseModel(BaseModel):
    _logger: Optional[logging.Logger] = pydantic.PrivateAttr(default=None)
    model_config = ConfigDict(extra="forbid")

    @property
    def logger(self):
        return self._logger

    def model_post_init(self, __context):
        self._logger = logging.getLogger(self.__class__.__name__)
        return super().model_post_init(__context)

    def model_dump(self, **kwargs):
        kwargs.setdefault("exclude_none", True)
        kwargs.setdefault("by_alias", True)
        return super().model_dump(**kwargs)
