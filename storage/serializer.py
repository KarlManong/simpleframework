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
        update: add constraint
        :param model: the model
        :param detail: if ``True``, will display all children's children
        if detail:
            will display children's children

            for e.g.:
                return '{"Order": [["SubOrder", 3], ["WorkCommand", 2]], "SubOrder":[["WorkCommand", 3]]}'
        else:
            will only display the children

            for e.g.:
                return '{"Order":[["SubOrder", 3], ["WorkCommand",2]]}'
        """

        def __mapper__(model):
            result = {model.__name__: [(child.__name__, constraint) for child, p, constraint in
                                       self.__func__.get_child_models(model)]}
            if detail:
                for child, p, constraint in self.__func__.get_child_models(model):
                    result.update(__mapper__(child))
            return result

        return json.dumps(__mapper__(model))

    def deserialize_model(self, string):
        """
        for e.g.:
            '{"SubOrder": [["WorkCommand", 2], ["StoreBill", 3]], "QIReport": [["StoreBill", 3]],
            "Order": [["SubOrder", 3]]}'
            will be analysed to Order -> [SubOrder, property1, 1], SubOrder->[WorkCommand, property2, 3]...
        """
        __mapper__ = json.loads(string)

        def _deserialize(mapper):
            result = {}
            for k, v in mapper.iteritems():
                k_model = self._get_model(k)
                result.setdefault(k_model, [])
                for i in v:
                    i_model = self._get_model(i[0] if isinstance(i, (list, tuple)) else i)
                    if i_model not in result[k_model]:
                        result[k_model].append((i_model, i[1] if isinstance(i, (list, tuple)) else None))
            return result

        def _get_property(parent_class, child_class, constraint):
            for pro in child_class.__mapper__.iterate_properties:
                if hasattr(pro, "direction") and pro.direction.name == "MANYTOONE" and \
                                pro.local_remote_pairs[0][1] in parent_class.__table__.columns._all_cols:
                    return child_class, pro, constraint if constraint is not None else (
                        constants.MAY if pro.local_remote_pairs[0][
                            0].nullable else constants.SHOULD)
            else:
                raise ValueError(u"关联错误%s: %s" % (parent_class.__name__, child_class.__name__))

        self.__func__.model_mapper_dict = {k: [_get_property(k, i[0], i[1]) for i in v] for k, v in
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
    from functions import DeleteModelFunction, register_test_delete_func, register_delete_permissions
    from lite_mms.apis.order import OrderWrapper

    register_delete_permissions()
    register_test_delete_func(models.Order)(
        lambda x: any(work_command.status == c.work_command.STATUS_FINISHED for work_command in
                      OrderWrapper(x).work_command_list))
    func = DeleteModelFunction(db.session)
    model_list = []
    for k, v in models.__dict__.items():
        if isinstance(v, types.TypeType) and issubclass(v, db.Model):
            model_list.append(v)
    func.registered_models = model_list
    serializer = JSONSerializer(func)
    print serializer.serialize_model(models.Order, True)
    print u"解析:"
    print u"\t{0:s}".format(serializer.deserialize_model(
        '{"Deduction": [], "StoreBill": [], "WorkCommand": [["QIReport", 3], ["Deduction", 3]], '
        '"SubOrder": [["WorkCommand", 2], ["StoreBill", 3]], "QIReport": [["StoreBill", 3]], "Order": [["SubOrder", '
        '1]]}'))
    order = models.Order.query.filter_by(id=415).one()
    print u"与{0:s}相关的所有对象:".format(order)
    print u"\t{0:s}".format(func.get_all_derivatives(order))

    # 当我想要删除order时：首先看它的删除条件
    print u"删除{0:s}的前提条件:".format(order)
    print u"\t{0:s}".format(func.get_conditions(order, detail=True))

    # 没有权限，则发送到有权限的人
    print u"通知："
    print u"\t{0:s}".format(func.notify_obj(order))
    # 等待对方操作

    # 然后删除
    func.do_action(order)
