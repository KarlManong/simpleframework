#-*- coding:utf-8 -*-
import types

if __name__ == "__main__":
    from lite_mms.basemain import app, db
    from lite_mms import models

    order = models.Order.query.filter_by(id=415).one()
    assert order
    import functions

    for k, v in models.__dict__.items():
        if hasattr(v, "_sa_class_manager"):
            functions.register_model(v)
    functions.set_session(session=db.session)
    print functions.get_children(order)
    print functions.get_all_derivatives(order)
    functions.delete_all(order)
    print functions.get_all_derivatives(order)
