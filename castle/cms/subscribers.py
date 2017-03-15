from castle.cms import audit
from castle.cms import tasks
from castle.cms.constants import DEFAULT_SITE_LAYOUT_REGISTRY_KEY
from castle.cms.lead import check_lead_image
from plone import api
from plone.api.exc import CannotGetPortalError
from plone.app.blocks.interfaces import DEFAULT_CONTENT_LAYOUT_REGISTRY_KEY
from plone.app.blocks.layoutbehavior import ILayoutAware
from plone.app.dexterity.behaviors.metadata import IOwnership
from plone.app.dexterity.behaviors.metadata import IPublication
from plone.app.event.base import localized_now
from plone.registry.interfaces import IRegistry
from plone.uuid.interfaces import IUUID
from Products.CMFCore.WorkflowCore import WorkflowException
from Products.CMFPlone.browser.syndication.settings import FeedSettings
from zope.component import getUtility
from zope.globalrequest import getRequest
from zope.interface import Interface


try:
    from z3c.relationfield.interfaces import IRelationBrokenEvent
except ImportError:
    class IRelationBrokenEvent(Interface):
        pass


def onFileEdit(obj, event):
    if IRelationBrokenEvent.providedBy(event):
        # these trigger too much!
        return

    try:
        tasks.file_edited.delay(obj)
    except CannotGetPortalError:
        pass


def onFileDelete(obj, event):
    try:
        tasks.aws_file_deleted.delay(IUUID(obj))
    except CannotGetPortalError:
        pass


def onFileStateChanged(obj, event):
    try:
        tasks.workflow_updated.delay(obj)
    except CannotGetPortalError:
        pass


def onContentCreated(obj, event):
    if obj.portal_type == 'Dashboard':
        return
    metadata = IPublication(obj, None)
    if metadata is not None:
        if metadata.effective is None:
            metadata.effective = localized_now(obj)
    _touchContributors(obj)

    if obj.portal_type == 'Collection':
        # enable syndication on type by default
        settings = FeedSettings(obj)
        settings.enabled = True

    adapted = ILayoutAware(obj, None)
    if adapted:
        if not adapted.content and not adapted.contentLayout:
            registry = getUtility(IRegistry)
            try:
                default_layout = registry['%s.%s' % (
                    DEFAULT_CONTENT_LAYOUT_REGISTRY_KEY,
                    obj.portal_type.replace(' ', '-'))]
                adapted.contentLayout = default_layout
            except (KeyError, AttributeError):
                pass
            try:
                default_layout = registry['%s.%s' % (
                    DEFAULT_SITE_LAYOUT_REGISTRY_KEY,
                    obj.portal_type.replace(' ', '-'))]
                adapted.pageSiteLayout = default_layout
            except (KeyError, AttributeError):
                pass

    try:
        tasks.scan_links.delay('/'.join(obj.getPhysicalPath()))
    except CannotGetPortalError:
        pass

    obj.reindexObject()


def onContentModified(obj, event):
    if IRelationBrokenEvent.providedBy(event):
        # these trigger too much!
        return
    if obj.portal_type == 'Dashboard':
        return
    try:
        tasks.scan_links.delay('/'.join(obj.getPhysicalPath()))
    except CannotGetPortalError:
        pass
    _touchContributors(obj)


def onEditFinished(obj, event):
    """
    on forms submission of done editing page...
    """
    check_lead_image(obj, request=getRequest())


def onObjectEvent(obj, event):
    if IRelationBrokenEvent.providedBy(event):
        # these trigger too much!
        return
    audit.event(obj, event)


def onPASEvent(event):
    audit.event(event)


def _touchContributors(obj):
    ownership = IOwnership(obj, None)
    if ownership is not None:
        # current user id
        try:
            user_id = api.user.get_current().getId()
            if (user_id not in ownership.creators and
                    user_id not in ownership.contributors):
                ownership.contributors = ownership.contributors + (user_id.decode('utf8'),)
        except:
            pass


def onTrashTransitioned(obj, event):
    api.portal.show_message(
        'You are not allowed to transition an item in the recycling bin.',
        request=getRequest(), type='error')
    raise WorkflowException('You are not allowed to transition an item in the recycling bin.')
