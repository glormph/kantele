from django import template
register = template.Library()


@register.tag(name='get_meta')
def get_metadata(parser, token):
    tagname, meta, fn, p = token.split_contents()
    return MetaDataValueNode(meta, fn, p)



class MetaDataValueNode(template.Node):
    def __init__(self, metadata, fn, p):
        self.meta = template.Variable(metadata)
        self.fn = template.Variable(fn)
        self.p = template.Variable(p)

    def render(self, context):
        try:
            meta = self.meta.resolve(context)
            fn = self.fn.resolve(context)
            p = self.p.resolve(context)
        except:
            raise

        if p in meta['files'][fn]:
            return meta['files'][fn][p] 
        else:
            return meta['metadata'][p]
