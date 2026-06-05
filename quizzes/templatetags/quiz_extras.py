from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary by key in templates."""
    if isinstance(dictionary, dict):
        return dictionary.get(str(key))
    return None


@register.filter
def percentage(value, total):
    """Calculate percentage."""
    try:
        return round((float(value) / float(total)) * 100, 1)
    except (ValueError, ZeroDivisionError):
        return 0


@register.filter
def letter_index(index):
    """Convert 0-based index to letter (a, b, c, d...)."""
    return chr(97 + index)


@register.filter
def subtract(value, arg):
    """Subtract arg from value."""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return 0
