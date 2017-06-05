import json


# FIXME this module seems ridiculous. Only contains order
class MetadataConfig(object):
    def __init__(self):
        with open('metadata_param_order.json') as fp:
            order = json.load(fp)
        self.paramorder = order['order']
