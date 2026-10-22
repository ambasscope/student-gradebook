from django import template
from config.numbers import compact_number

register = template.Library()
register.filter("compact_number", compact_number)
