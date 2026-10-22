"""Optional bilingual suggestions, independent from saved module schemes."""
from django.utils.translation import get_language
from ..models import MarkingSchemeCategory
from config.numbers import compact_number


def display_name(item):
    key = "name_th" if (get_language() or "en").startswith("th") else "name_en"
    return item.get(key) or item.get("name_th") or item.get("name_en") or ""


def category_catalog():
    result = []
    for category in MarkingSchemeCategory.objects.all():
        record = {"id": category.pk, "name_th": category.name_th, "name_en": category.name_en}
        record["name"] = display_name(record)
        record["items"] = [{**item, "name": display_name(item), "maximum": compact_number(item.get("maximum")),
                            "weight": compact_number(item.get("weight", 1))} for item in category.subcategories]
        result.append(record)
    return result
