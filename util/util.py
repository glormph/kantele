def convert_dicts_unicode_to_utf8(d):
    if isinstance(d, dict):
        return { convert_dicts_unicode_to_utf8(k): \
            convert_dicts_unicode_to_utf8(v) for k,v in d.items() }
    elif isinstance(d, list):
        return [convert_dicts_unicode_to_utf8(x) for x in d]
    elif isinstance(d, unicode):
        return d.encode('utf-8')
    else:
        return d
