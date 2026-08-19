"""
Setu's register layer.

Register is a first-class control, not a side effect. This package is the part
of the system that makes that true: it reads the politeness level a speaker
used, rewrites a translation into a requested level, and shows the user exactly
which rules fired to get there.

It is deliberately engine-agnostic and dependency-free. Whatever ASR, MT and
TTS the pipeline is wired to this month, the register layer sits above all of
them and is the final arbiter of the output. That is also why it is the one
stage that keeps working with no network at all.

    >>> from register import rewrite, detect, ladder, POLITE
    >>> rewrite("তুমি কি করছ?", "bn", POLITE).text
    'আপনি কি করছেন?'
    >>> detect("আপনি কেমন আছেন?", "bn").level == POLITE
    True
"""

from .levels import (
    AUTO,
    CASUAL,
    CLOSE,
    FORMAL,
    LEVEL_NAMES,
    LEVEL_SLUGS,
    LEVELS,
    POLITE,
    coerce_level,
    formality_percent,
    level_from_percent,
    level_name,
    level_slug,
)
from .engine import (
    Detection,
    Edit,
    RewriteResult,
    address_term,
    detect,
    ladder,
    politeness_warning,
    pre_edit,
    prosody,
    rewrite,
)
from .tables import (
    TABLES,
    LanguageTable,
    Rule,
    get_table,
    has_table,
    supported_languages,
)
from .social import (
    CORNERS,
    RELATIONSHIPS,
    describe as describe_relationship,
    expected_in,
    level_for,
    level_in,
)

__all__ = [
    # levels
    "CLOSE",
    "CASUAL",
    "POLITE",
    "FORMAL",
    "LEVELS",
    "LEVEL_NAMES",
    "LEVEL_SLUGS",
    "AUTO",
    "coerce_level",
    "level_name",
    "level_slug",
    "formality_percent",
    "level_from_percent",
    # engine
    "rewrite",
    "detect",
    "ladder",
    "pre_edit",
    "prosody",
    "address_term",
    "RELATIONSHIPS",
    "CORNERS",
    "level_for",
    "level_in",
    "expected_in",
    "describe_relationship",
    "politeness_warning",
    "RewriteResult",
    "Detection",
    "Edit",
    # tables
    "TABLES",
    "LanguageTable",
    "Rule",
    "get_table",
    "has_table",
    "supported_languages",
]

__version__ = "0.2.0"
