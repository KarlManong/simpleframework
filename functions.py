#-*- coding:utf-8 -*-
import types
from functools import wraps
import constants


def _raise_when_models_empty(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.registered_models:
            raise RuntimeError(u"未注册models")
        return func(self, *args, **kwargs)

    return wrapper


class ModelFunction(object):
    model_test_delete_funcs = {}

    def __init__(self, session=None):
        self.__session__ = session
        self.registered_models = []
        self.model_mapper_dict = {}

    def register_model(self, model):
        if model not in self.registered_models:
            self.registered_models.append(model)

    def get_session(self, obj):
        if self.__session__ is None:
            return obj._sa_instance_state.session
        else:
            return self.__session__

    @_raise_when_models_empty
    def get_child_models(self, class_):
        """
        只能是one to many的， 相同的model只返回一次
        :param class_: the model class
        :type class_: types.TypeType
        :return a list of model class: [(model, property, constraint(MAY, SHOULD, MUST))]
        """
        assert isinstance(class_, types.TypeType) and hasattr(class_, "_sa_class_manager")
        if class_ not in self.model_mapper_dict:
            self.model_mapper_dict[class_] = []
            for loop in self.registered_models:
                if loop != class_:
                    for pro in loop.__mapper__.iterate_properties:
                        if hasattr(pro, "direction") and pro.direction.name == "MANYTOONE" and \
                                        pro.local_remote_pairs[0][1] in class_.__table__.columns._all_cols:
                            constraint = constants.MAY
                            if not pro.local_remote_pairs[0][0].nullable:
                                constraint = constants.SHOULD
                            self.model_mapper_dict[class_].append((loop, pro, constraint))
        return self.model_mapper_dict[class_]

    @_raise_when_models_empty
    def get_children_generate(self, obj):
        for model, pro, constraint in self.get_child_models(obj.__class__):
            for i in self.get_session(obj).query(model).filter(pro.class_attribute == obj):
                yield i

    @_raise_when_models_empty
    def get_children(self, obj):
        return list(self.get_children_generate(obj))

    @_raise_when_models_empty
    def get_all_derivatives(self, obj):
        return [{child: self.get_all_derivatives(child)} for child in self.get_children_generate(obj)]

    @_raise_when_models_empty
    def delete_all(self, obj):
        """
        删除一个obj的规则为： 1、测试该obj是否可以删除，如果不能删除则抛出异常
                           2、真正的删除该obj
            其中判断obj是否可以删除，框架无法做到，需要obj本身或者是基于该obj的扩展类给出结果。
            因此需要该obj提供对应的方法。
        """
        if self.test_delete(obj):
            for child in self.get_children(obj):
                self.delete_all(child)
            try:
                self.delete(obj)
            except:
                raise
        else:
            raise ValueError(self.get_delete_conditions(obj.__class__))

    def get_delete_conditions(self, model_class):
        def __delete_condition__(model_class):
            conditions = []
            for model, pro, con in self.get_child_models(model_class):
                conditions.append(constants.constraints[con](model))
                conditions.extend(__delete_condition__(model))
            return conditions

        return __delete_condition__(model_class)

    def test_delete(self, obj):
        """
        从注册的方法中判断该obj是否可以删除
        """
        func = ModelFunction.model_test_delete_funcs.get(obj.__class__)
        if func:
            try:
                func(obj)
            except TypeError:
                func(func.im_class(obj))
        else:
            return False

    def delete(self, obj):
        session = self.get_session(obj)
        session.delete(obj)
        try:
            session.commit()
        except:
            session.rollback()


def register_test_delete_func(class_):
    """
    @:param class_: 这里应该是具体的class类
    """

    def decorate(func):
        ModelFunction.model_test_delete_funcs[class_] = func

        @wraps(func)
        def f(*args, **kwargs):
            return func(*args, **kwargs)

        return f

    return decorate


if __name__ == "__main__":
    from lite_mms.basemain import app, db
    from lite_mms import models

    order = models.Order.query.filter_by(id=415).one()
    assert order
    func = ModelFunction(db.session)
    for k, v in models.__dict__.items():
        if isinstance(v, types.TypeType) and issubclass(v, db.Model):
            func.register_model(v)
    print func.get_child_models(models.Order)
    print func.get_children(order)
    print func.model_mapper_dict
