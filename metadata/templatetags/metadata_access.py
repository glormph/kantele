from django import template
register = template.Library()

@register.filter(name="lookup")
def lookup(d, key):
    return d[key]
