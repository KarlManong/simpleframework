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
            will be analysed to Order -> [SubOrder, property1, 1], SubOrder->[WorkCommand, property2, 3]...
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

        def _get_property(parent_class, child_class):
            for pro in child_class.__mapper__.iterate_properties:
                if hasattr(pro, "direction") and pro.direction.name == "MANYTOONE" and \
                                pro.local_remote_pairs[0][1] in parent_class.__table__.columns._all_cols:
                    return child_class, pro, constants.MAY if pro.local_remote_pairs[0][
                        0].nullable else constants.SHOULD
            else:
                raise ValueError(u"关联错误%s: %s" % (parent_class.__name__, child_class.__name__))

        self.__func__.model_mapper_dict = {k: [_get_property(k, i) for i in v] for k, v in
                                           _deserialize(__mapper__).iteritems()}
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
    from lite_mms import models, constants as c
    from functions import ModelFunction, register_test_delete_func
    from lite_mms.apis.order import OrderWrapper

    register_test_delete_func(models.Order)(
        lambda x: any(work_command.status == c.work_command.STATUS_FINISHED for work_command in
                      OrderWrapper(x).work_command_list))
    func = ModelFunction(db.session)
    model_list = []
    for k, v in models.__dict__.items():
        if isinstance(v, types.TypeType) and issubclass(v, db.Model):
            model_list.append(v)
    func.registered_models = model_list
    serializer = JSONSerializer(func)
    # print serializer.serialize_model(models.Order, True)
    print u"解析:"
    print u"\t%s" % serializer.deserialize_model(
        '{"Order": [{"SubOrder": [{"WorkCommand": [{"QIReport": [{"StoreBill": []}]}, {"QIReport": [{"StoreBill": ['
        ']}]}, {"Deduction": []}]}, {"StoreBill": []}]}]}')
    order = models.Order.query.filter_by(id=415).one()
    print u"与%s相关的所有对象:" % unicode(order)
    print u"\t%s" % func.get_all_derivatives(order)

    # 当我想要删除order时：首先看它的删除条件
    print u"删除%s的前提条件:" % unicode(order)
    print u"\t%s" % func.get_delete_conditions(order, detail=True)
    # 然后删除
    func.delete_all(order)
