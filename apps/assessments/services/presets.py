"""New module drafts use the current, editable marking library."""
from django.utils.translation import gettext
from .marking_library import category_catalog

DEFAULT_PRESET = "marking_library"


def default_scheme():
    # Subcategories are optional suggestions. Teachers choose the ones to assess
    # and supply maximum marks; the reference file does not prescribe maxima.
    return [{"name": item["name"], "learning_objective": "", "weight": "0", "items": []}
            for item in category_catalog()[:30]]


def preset_catalog():
    return [{"id": DEFAULT_PRESET, "name": gettext("My marking scheme library"),
             "mode": "points", "scheme": default_scheme()}]
