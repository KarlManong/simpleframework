#-*- coding:utf-8 -*-
import functions

try:
    import simplejson as json
except ImportError:
    import json


class Serializer(object):
    def serialize_model(self, *args, **kwargs):
        raise NotImplementedError


class XMLSerializer(Serializer):
    def serialize_model(self, *args, **kwargs):
        pass


class JSONSerializer(Serializer):
    """
    for e.g.:
        {Order:[SubOrder:[WorkCommand]]}
    """

    def __init__(self, models=None):
        if models:
            functions.register_models(models)

    def serialize_model(self, model):
        def __mapper__(model):
            return {model.__name__: [__mapper__(child) for child, p in functions.get_child_models(model)]}

        return json.dumps(__mapper__(model))

    def deserialize_model(self, *args, **kwargs):
        pass


if __name__ == "__main__":
    import types
    from lite_mms.basemain import app, db
    from lite_mms import models

    model_list = []
    for k, v in models.__dict__.items():
        if isinstance(v, types.TypeType) and issubclass(v, db.Model):
            model_list.append(v)
    serializer = JSONSerializer(model_list)
    print serializer.serialize_model(models.Order)