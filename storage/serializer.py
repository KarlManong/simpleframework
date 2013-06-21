#-*- coding:utf-8 -*-
try:
    import simplejson as json
except ImportError:
    import json

import constants


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

        # self.__func__.model_mapper_dict = _deserialize(__mapper__) 这样的话，对应的Property不知道
        def _get_property(parent_class, child_class):
            for pro in child_class.__mapper__.iterate_properties:
                if hasattr(pro, "direction") and pro.direction.name == "MANYTOONE" and \
                                pro.local_remote_pairs[0][1] in parent_class.__table__.columns._all_cols:
                    constraint = constants.MAY
                    if not pro.local_remote_pairs[0][0].nullable:
                        constraint = constants.SHOULD
                    return child_class, pro, constraint
            else:
                raise ValueError(u"关联错误%s: %s" % (parent_class.__name__, child_class.__name__))

        self.__func__.model_mapper_dict = {}
        for k, v in _deserialize(__mapper__).iteritems():
            self.__func__.model_mapper_dict[k] = []
            for i in v:
                self.__func__.model_mapper_dict[k].append(_get_property(k, i))
        return self.__func__.model_mapper_dict

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
    order = models.Order.query.filter_by(id=415).one()
    print func.get_all_derivatives(order)

    # 当我想要删除order时：
    func.delete_all(order)
