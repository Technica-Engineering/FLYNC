"""
Private mixin classes that compose :class:`~flync.model.flync_model.FLYNCModel`.

These are internal implementation details: split out of the top-level model to keep
:file:`flync_model.py` within a manageable size. Nothing here is part of the public API;
import the aggregate ``FLYNCModel`` from ``flync.model`` instead.
"""

from flync.model._model_parts._accessors import AccessorMixin
from flync.model._model_parts._binding import BindingMixin
from flync.model._model_parts._multicast import MulticastMixin

# These mixins are the body of ``flync.model.flync_model`` split out, so their warning/error call
# sites must resolve to the same ``GEN`` module code as the top-level model itself.
KEY = "GEN"

__all__ = ["AccessorMixin", "BindingMixin", "MulticastMixin"]
