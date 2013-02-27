import json

class MetadataConfig(object):
    def __init__(self):
        with open('metadata_param_order.json') as fp:
            order = json.load(fp)
        
        self.paramorder = order['order']
