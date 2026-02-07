from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Return a dictionary value for an integer key with a default of 0.

    :param dictionary: Mapping of integer keys to values.
    :param key: Key value supplied by the template.
    :return: Value for the key or 0 if missing.
    :rtype: int
    """
    return dictionary.get(int(key), 0)
