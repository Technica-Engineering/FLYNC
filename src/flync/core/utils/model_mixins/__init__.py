"""
Mixin classes that compose :class:`~flync.model.flync_model.FLYNCModel`.

Query, binding and multicast behavior of the top-level model, split out of ``flync_model.py`` to keep it
within a manageable size. ``FLYNCModel`` inherits them, so their methods are part of its public API;
import the aggregate ``FLYNCModel`` from ``flync.model`` rather than using these classes directly.

Error and warning ids raised from here carry the ``CMN`` module code, like the rest of ``flync.core``.
"""

from flync.core.utils.model_mixins.accessors import AccessorMixin
from flync.core.utils.model_mixins.binding import BindingMixin
from flync.core.utils.model_mixins.multicast import MulticastMixin

__all__ = ["AccessorMixin", "BindingMixin", "MulticastMixin"]
