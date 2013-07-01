#-*- coding:utf-8 -*-
from zope.wfmc import process, interfaces
from zope.wfmc.attributeintegration import AttributeIntegration
import zope.component
import zope.interface


def log_event(event):
    print event


import zope.event

zope.event.subscribers.append(log_event)

integration = AttributeIntegration()
Publication = process.ProcessDefinition("publication")
Publication.integration = integration
zope.component.provideUtility(Publication, name=Publication.id)
Publication.defineActivities(start=process.ActivityDefinition("Start"),
                             prepare=process.ActivityDefinition("Prepare"),
                             tech1=process.ActivityDefinition("Technical Review 1"),
                             tech2=process.ActivityDefinition("Technical Review 2"),
                             review=process.ActivityDefinition("Editorial Review"),
                             final=process.ActivityDefinition("Final Preparation"),
                             rfinal=process.ActivityDefinition("Review Final"),
                             publish=process.ActivityDefinition("Publish"),
                             reject=process.ActivityDefinition("Reject"))
Publication.defineTransitions(
    process.TransitionDefinition('start', 'prepare'),
    process.TransitionDefinition('prepare', 'tech1'),
    process.TransitionDefinition('prepare', 'tech2'),
    process.TransitionDefinition('tech1', 'review'),
    process.TransitionDefinition('tech2', 'review'),

    process.TransitionDefinition(
        'review', 'reject',
        condition=lambda data: not data.publish
    ),
    process.TransitionDefinition(
        'review', 'prepare',
        condition=lambda data: data.tech_changes
    ),
    process.TransitionDefinition(
        'review', 'final',
        condition=lambda data: data.ed_changes
    ),
    process.TransitionDefinition('review', 'publish'),

    process.TransitionDefinition('final', 'rfinal'),
    process.TransitionDefinition(
        'rfinal', 'final',
        condition=lambda data: data.ed_changes
    ),
    process.TransitionDefinition('rfinal', 'publish'),
)
Publication.activities["prepare"].andSplit(True)
Publication.activities["review"].andJoin(True)
Publication.defineParticipants(author=process.Participant("Author"), tech1=process.Participant("Technical Reviewer 1"),
                               tech2=process.Participant("Technical Reviewer 2"),
                               reviewer=process.Participant("Editorial Reviewer"))

Publication.defineApplications(
    prepare=process.Application(),
    tech_review=process.Application(
        process.OutputParameter('publish'),
        process.OutputParameter('tech_changes'),
    ),
    ed_review=process.Application(
        process.InputParameter('publish1'),
        process.InputParameter('tech_changes1'),
        process.InputParameter('publish2'),
        process.InputParameter('tech_changes2'),
        process.OutputParameter('publish'),
        process.OutputParameter('tech_changes'),
        process.OutputParameter('ed_changes'),
    ),
    publish=process.Application(),
    reject=process.Application(),
    final=process.Application(),
    rfinal=process.Application(
        process.OutputParameter('ed_changes'),
    ),
)
Publication.activities["prepare"].definePerformer("author")
Publication.activities["prepare"].addApplication("prepare")
Publication.activities["tech1"].definePerformer("tech1")
Publication.activities["tech1"].addApplication("tech_review", ["publish1", "tech_changes1"])
Publication.activities["tech2"].definePerformer("tech2")
Publication.activities["tech2"].addApplication("tech_review", ["publish2", "tech_changes2"])
Publication.activities["review"].definePerformer("reviewer")
Publication.activities["review"].addApplication("ed_review",
                                                ["publish1", "tech_changes1", "publish2", "tech_changes2", "publish",
                                                 "tech_changes", "ed_changes"])
Publication.activities["final"].definePerformer("author")
Publication.activities["final"].addApplication("final")
Publication.activities["rfinal"].definePerformer("reviewer")
Publication.activities["rfinal"].addApplication("rfinal", ["ed_changes"])
Publication.activities["publish"].addApplication("publish")
Publication.activities["reject"].addApplication("reject")

Publication.defineParameters(process.InputParameter("author"), process.OutputParameter("publish"))


class User(object):
    def __init__(self):
        self.work_list = []


authors = {"bob": User(), "ted": User(), "sally": User()}
reviewer = User()
tech1 = User()
tech2 = User()


class Participant(object):
    zope.component.adapts(interfaces.IActivity)
    zope.interface.implements(interfaces.IParticipant)

    def __init__(self, activity):
        self.activity = activity


class Author(Participant):
    def __init__(self, activity):
        super(Author, self).__init__(activity)
        author_name = activity.process.workflowRelevantData.author
        print "Author '{}' selected".format(author_name)
        self.user = authors[author_name]


integration.authorParticipant = Author


class Reviewer(Participant):
    user = reviewer


integration.reviewerParticipant = Reviewer


class Tech1(Participant):
    user = tech1


integration.tech1Participant = Tech1


class Tech2(Participant):
    user = tech2


integration.tech2Participant = Tech2

integration.Participant = Participant


class ApplicationBase(object):
    zope.component.adapts(interfaces.IParticipant)
    zope.interface.implements(interfaces.IWorkItem)

    def __init__(self, participant):
        self.participant = participant
        self.activity = participant.activity
        participant.user.work_list.append(self)

    def start(self):
        pass

    def finish(self):
        self.participant.activity.workItemFinished(self)


class Prepare(ApplicationBase):
    def summary(self):
        process = self.activity.process
        doc = getattr(process.applicationRelevantData, "doc", "")
        if doc:
            print "Previous draft:"
            print doc
            print "Changes we need to make:"
            for change in process.workflowRelevantData.tech_changes:
                print change
        else:
            print "Please write the initial draft"

    def finish(self, doc):
        self.activity.process.applicationRelevantData.doc = doc
        super(Prepare, self).finish()


integration.prepareWorkItem = Prepare


class TechReview(ApplicationBase):
    def getDoc(self):
        return self.activity.process.applicationRelevantData.doc

    def finish(self, decision, changes):
        self.activity.workItemFinished(self, decision, changes)


integration.tech_reviewWorkItem = TechReview


class Review(TechReview):
    def start(self, publish1, changes1, publish2, changes2):
        if not (publish1 and publish2):
            self.activity.workItemFinished(self, False, changes1 + changes2, ())

        if changes1 or changes2:
            self.activity.workItemFinished(self, True, changes1 + changes2, ())


    def finish(self, ed_changes):
        self.activity.workItemFinished(self, True, (), ed_changes)


integration.ed_reviewWorkItem = Review


class Final(ApplicationBase):
    def summary(self):
        process = self.activity.process
        doc = getattr(process.applicationRelevantData, "doc", "")
        print "Previous draft:"
        print self.activity.process.applicationRelevantData.doc
        print "Changes we need to make:"
        for change in process.workflowRelevantData.ed_changes:
            print change

    def finish(self, doc):
        self.activity.process.applicationRelevantData.doc = doc
        super(Final, self).finish()


integration.finalWorkItem = Final


class ReviewFinal(TechReview):
    def finish(self, ed_changes):
        self.activity.workItemFinished(self, ed_changes)


integration.rfinalWorkItem = ReviewFinal


class Publish:
    zope.component.adapts(interfaces.IParticipant)
    zope.interface.implements(interfaces.IWorkItem)

    def __init__(self, participant):
        self.participant = participant

    def start(self):
        print "Published"
        self.finish()

    def finish(self):
        self.participant.activity.workItemFinished(self)


integration.publishWorkItem = Publish


class Reject(Publish):
    def start(self):
        print "Rejected"
        self.finish()


integration.rejectWorkItem = Reject


class PublicationContext:
    zope.interface.implements(interfaces.IProcessContext)

    def processFinished(self, process, decision):
        self.decision = decision


context = PublicationContext()
proc = Publication(context)
proc.start("bob")
item = authors["bob"].work_list.pop()
item.finish("I give my pledge, as an American\n"
            "to save, and faithfully to defend from waste\n"
            "the natural resources of my Country.")

item = tech1.work_list.pop()
print item.getDoc()
item.finish(True, [])
item = tech2.work_list.pop()
item.finish(True, [])
item = reviewer.work_list.pop()
print item.getDoc()

item.finish(['change "an" to "a"'])
item = authors["bob"].work_list.pop()
item.summary()
item.finish("I give my pledge, as a human\n"
            "to save, and faithfully to defend from waste\n"
            "the natural resources of my planet.")

item = reviewer.work_list.pop()
print item.getDoc()

item.finish([])
print context.decision
