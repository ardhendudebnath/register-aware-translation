"""Draft register sets, grouped by language family."""

from . import dravidian, indo_aryan, western

#: Every set except Bengali, which keeps its own hand-written builder
#: (``data/gold/build_bn.py``) because it is the reference set the others
#: are modelled on.
ALL = indo_aryan.ALL + dravidian.ALL + western.ALL

BY_CODE = {language.code: language for language in ALL}

__all__ = ["ALL", "BY_CODE", "indo_aryan", "dravidian", "western"]
