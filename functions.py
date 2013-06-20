#-*- coding:utf-8 -*-
import types
from functools import wraps

__models__ = []
__session__ = None
__test_delete_funcs__ = {}
__model_mapper__ = {}

MUST = 1
SHOULD = 2
MAY = 3


def _raise_when_models_empty(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not __models__:
            raise RuntimeError(u"未注册models")
        return func(*args, **kwargs)

    return wrapper


def register_models(models):
    for model in models:
        register_model(model)


def register_model(model):
    if model not in __models__:
        __models__.append(model)


def get_registered_models():
    return __models__


@_raise_when_models_empty
def get_child_models(class_):
    """
    只能是one to many的， 相同的model只返回一次
    :param class_: the model class
    :type class_: types.TypeType
    :return a list of model class
    """
    assert isinstance(class_, types.TypeType) and hasattr(class_, "_sa_class_manager")
    if class_ not in __model_mapper__:
        __model_mapper__[class_] = []
        for loop in __models__:
            if loop != class_:
                for pro in loop.__mapper__.iterate_properties:
                    if hasattr(pro, "direction") and pro.direction.name == "MANYTOONE" and \
                                    pro.local_remote_pairs[0][1] in class_.__table__.columns._all_cols:
                        __model_mapper__[class_].append((loop, pro))
    return __model_mapper__[class_]


@_raise_when_models_empty
def get_children_generate(obj):
    for model, pro in get_child_models(obj.__class__):
        for i in get_session(obj).query(model).filter(pro.class_attribute == obj):
            yield i


@_raise_when_models_empty
def get_children(obj):
    return list(get_children_generate(obj))


@_raise_when_models_empty
def get_all_derivatives(obj):
    return [{child: get_all_derivatives(child)} for child in get_children_generate(obj)]


def set_session(session):
    global __session__
    __session__ = session


def get_session(obj):
    if __session__ is None:
        return obj._sa_instance_state.session
    else:
        return __session__


@_raise_when_models_empty
def delete_all(obj):
    """
    删除一个obj的规则为： 1、测试该obj是否可以删除，如果不能删除则抛出异常
                       2、真正的删除该obj
        其中判断obj是否可以删除，框架无法做到，需要obj本身或者是基于该obj的扩展类给出结果。
        因此需要该obj提供对应的方法。
    """
    if test_delete(obj):
        for child in get_children(obj):
            delete_all(child)
        try:
            delete(obj)
        except:
            raise
    else:
        raise ValueError(u"不能删除")


def test_delete(obj):
    """
    从注册的方法中判断该obj是否可以删除
    """
    func = __test_delete_funcs__.get(obj.__class__)
    if func:
        try:
            func(obj)
        except TypeError:
            func(func.im_class(obj))
    else:
        return False


def register_test_delete_func(class_):
    """
    @:param class_: 这里应该是具体的class类
    """

    def decorate(func):
        global __test_delete_funcs__
        __test_delete_funcs__[class_] = func

        @wraps(func)
        def f(*args, **kwargs):
            return func(*args, **kwargs)

        return f

    return decorate


def delete(obj):
    session = get_session(obj)
    session.delete(obj)
    try:
        session.commit()
    except:
        session.rollback()


if __name__ == "__main__":
    from lite_mms.basemain import app, db
    from lite_mms import models

    order = models.Order.query.filter_by(id=415).one()
    assert order
    for k, v in models.__dict__.items():
        if isinstance(v, types.TypeType) and issubclass(v, db.Model):
            register_model(v)
    set_session(session=db.session)
    print get_children(order)
    print get_child_models(models.Order)
