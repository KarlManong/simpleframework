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
    def __init__(self, func):
        """
        :param func: an instance of ModelFunction
        :type func: ModelFunction
        """
        self.__func__ = func

    def serialize_model(self, model, detail=False):
        """
        :param model: the model
        :param detail: if ``True``, will display all children's children
        if detail:
            will display children's children

            for e.g.:
                return '{"Order": [
                            {"SubOrder": [
                                {"WorkCommand":
                                    [{"QIReport": [{"StoreBill": []}]},
                                    {"Deduction": []}]}}'
        else:
            will only display the children

            for e.g.:
                return '{"Order":["SubOrder"]}'
        """

        def __mapper__(model):
            return {model.__name__: [
                __mapper__(child) if detail else child.__name__ for child, p in self.__func__.get_child_models(model)]}

        return json.dumps(__mapper__(model))

    def deserialize_model(self, string):
        """
        for e.g.:
            '{"Order": [{"SubOrder": [{"WorkCommand": [{"QIReport": [{"StoreBill": []}]}, {"Deduction": []}]}}'
            will be analysed to Order -> [SubOrder], SubOrder->[WorkCommand]...
        """
        __mapper__ = json.loads(string)

        def _deserialize(mapper):
            result = {}
            for k, v in mapper.iteritems():
                k_model = self._get_model(k)
                result.setdefault(k_model, [])
                for i in v:
                    if isinstance(i, dict):
                        for key in i.iterkeys():
                            key_model = self._get_model(key)
                            if key_model not in result[k_model]:
                                result[k_model].append(key_model)
                        result.update(_deserialize(i))
                    else:
                        i_model = self._get_model(i)
                        if i_model not in result[k_model]:
                            result[k_model].append(i_model)
            return result

        return _deserialize(__mapper__)

    def _get_model(self, model_name, default=None):
        for model in self.__func__.registered_models:
            if model.__name__ == model_name:
                return model
        else:
            return default


if __name__ == "__main__":
    import types
    from lite_mms.basemain import app, db
    from lite_mms import models
    from functions import ModelFunction

    func = ModelFunction(db.session)
    model_list = []
    for k, v in models.__dict__.items():
        if isinstance(v, types.TypeType) and issubclass(v, db.Model):
            model_list.append(v)
    func.registered_models = model_list
    serializer = JSONSerializer(func)
    # print serializer.serialize_model(models.Order, True)
    print serializer.deserialize_model(
        '{"Order": [{"SubOrder": [{"WorkCommand": [{"QIReport": [{"StoreBill": []}]}, {"QIReport": [{"StoreBill": ['
        ']}]}, {"Deduction": []}]}, {"StoreBill": []}]}]}')