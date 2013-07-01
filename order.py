#-*- coding:utf-8 -*-
from zope.wfmc import process, interfaces
from zope.wfmc.attributeintegration import AttributeIntegration
import zope.interface
import zope.component

integration = AttributeIntegration()
pd = process.ProcessDefinition("delete order")


def log_event(event):
    print event


zope.event.subscribers.append(log_event)

pd.integration = integration
zope.component.provideUtility(pd, name=pd.id)

pd.defineActivities(start=process.ActivityDefinition("start"),
                    delete_order=process.ActivityDefinition("delete order"),
                    delete_sub_order=process.ActivityDefinition("delete sub_order"),
                    d_s_o_approve=process.ActivityDefinition("delete sub_order approved"),
                    d_s_o_deny=process.ActivityDefinition("delete sub_order denied"),
                    d_o_approve=process.ActivityDefinition("delete order approved"),
                    d_o_deny=process.ActivityDefinition("delete order denied"),
                    finish=process.ActivityDefinition("finish")
)
pd.defineTransitions(process.TransitionDefinition("start", "delete_sub_order"),
                     process.TransitionDefinition("delete_sub_order", "d_s_o_approve"),
                     process.TransitionDefinition("delete_sub_order", "d_s_o_deny"),
                     process.TransitionDefinition("d_s_o_approve", "delete_order"),
                     process.TransitionDefinition("d_s_o_deny", "finish"),
                     process.TransitionDefinition("delete_order", "d_o_approve"),
                     process.TransitionDefinition("delete_order", "d_o_deny"),
                     process.TransitionDefinition("d_o_deny", "finish"),
                     process.TransitionDefinition("d_o_approve", "finish")
)
pd.activities["delete_sub_order"].andSplit(True)
pd.activities["delete_order"].andJoin(True)


class Participant(object):
    zope.component.adapts(interfaces.IActivity)
    zope.interface.implements(interfaces.IParticipant)

    def __init__(self, activity):
        self.activity = activity


class Order(object):
    pass


class SubOrder(object):
    pass


integration.participant = Participant

proc = pd()
proc.start()
