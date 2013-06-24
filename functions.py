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
    model_test_funcs = {}
    model_permissions = {}

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
                            self.model_mapper_dict[class_].append((loop, pro,
                                                                   constants.MAY if pro.local_remote_pairs[0][
                                                                       0].nullable else constants.SHOULD))
                            break
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


    def get_conditions(self, obj, detail):
        """
        :param obj: the object to be manager
        :param detail: if detail is True, show all the generato
        """
        raise NotImplementedError

    def test_obj(self, obj):
        func = self.model_test_funcs.get(obj.__class__)
        if func:
            try:
                return func(obj)
            except TypeError:
                return func(func.im_class(obj))
        else:
            return True

    def _notify(self, obj, user):
        raise NotImplementedError

    def notify_user(self, obj):
        def _get_users(permission):
            #TODO 伪实现
            from lite_mms import models

            return models.User.query.filter(models.User.id == 3).all()

        for child, constrain in self.get_conditions(obj, True):
            if constrain < constants.MAY:
                for k, v in self.model_permissions.iteritems():
                    if child.__class__.__name__ == k:
                        for user in _get_users(v):
                            self._notify(child, user)

    @_raise_when_models_empty
    def do_action(self, obj):
        raise NotImplementedError


class DeleteModelFunction(ModelFunction):
    def get_conditions(self, obj, detail):
        def __model_relationships__(obj):
            conditions = []
            for child in self.get_children(obj):
                for model, prop, constraint in self.model_mapper_dict[obj.__class__]:
                    if child.__class__ == model:
                        conditions.append((child, constraint))
                        if detail:
                            conditions.extend(__model_relationships__(child))
            return conditions

        return __model_relationships__(obj)

    def delete(self, obj):
        session = self.get_session(obj)
        session.delete(obj)
        try:
            session.commit()
        except:
            session.rollback()

    def _notify(self, obj, user):
        #TODO 伪实现
        print u"请求删除{0:s}".format(str(obj))

    @_raise_when_models_empty
    def do_action(self, obj):
        """
        删除一个obj的规则为： 1、测试该obj是否可以删除，如果不能删除则抛出异常
                           2、真正的删除该obj
            其中判断obj是否可以删除，框架无法做到，需要obj本身或者是基于该obj的扩展类给出结果。
            因此需要该obj提供对应的方法。
        """
        try:
            if self.test_obj(obj):
                conditions = self.get_conditions(obj, True)
                if conditions:
                    raise ValueError(conditions)
                for child in self.get_children(obj):
                    self.do_action(child)
                self.delete(obj)
            else:
                raise ValueError(u"不能删除")
        except:
            raise


class ModifyModelFunction(ModelFunction):
    def get_conditions(self, obj, detail):
        def __model_relationships__(obj):
            conditions = []
            for child in self.get_children(obj):
                for model, prop, constraint in self.model_mapper_dict[obj.__class__]:
                    if child.__class__ == model:
                        conditions.append((child, constraint))
                        if detail:
                            conditions.extend(__model_relationships__(child))
            return conditions

        return __model_relationships__(obj)

    def modify(self, obj):
        session = self.get_session(obj)
        session.update(obj)
        try:
            session.commit()
        except:
            session.rollback()

    @_raise_when_models_empty
    def do_action(self, obj):
        try:
            if self.test_obj(obj):
                conditions = self.get_conditions(obj, True)
                if conditions:
                    raise ValueError(conditions)
                for child in self.get_children(obj):
                    self.do_action(child)
                self.modify(obj)
            else:
                raise ValueError(u"不能修改")
        except:
            raise

    def _notify(self, obj, user):
        print u"请求修改{}".format(str(obj))


def register_test_delete_func(class_):
    """
    :param class_: 这里应该是具体的class类
    """

    def decorate(func):
        DeleteModelFunction.model_test_funcs[class_] = func

        @wraps(func)
        def f(*args, **kwargs):
            return func(*args, **kwargs)

        return f

    return decorate


def register_delete_permissions():
    #TODO 伪实现
    from lite_mms.permissions import SchedulerPermission

    DeleteModelFunction.model_permissions = {"WorkCommand": SchedulerPermission}


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
