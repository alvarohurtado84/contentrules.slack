# -*- coding: utf-8 -*-
from contentrules.slack import _
from contentrules.slack import SLACK_WEBHOOK_URL
from ftw.slacker import notify_slack
from OFS.SimpleItem import SimpleItem
from plone.app.contentrules.actions import ActionAddForm
from plone.app.contentrules.actions import ActionEditForm
from plone.app.contentrules.browser.formhelper import ContentRuleFormWrapper
from plone.contentrules.rule.interfaces import IExecutable
from plone.contentrules.rule.interfaces import IRuleElementData
from plone.stringinterp.interfaces import IStringInterpolator
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from zope import schema
from zope.component import adapter
from zope.interface import implementer
from zope.interface import Interface

import logging


logger = logging.getLogger('contentrules.slack')


class ISlackAction(Interface):
    """Definition of the configuration available for a slack action."""

    webhook_url = schema.URI(
        title=_(u'Webhook url'),
        description=_(
            u'URL configuration for this integration. '
            u'i.e.:"https://hooks.slack.com/services/T00000000/B00000000/YYYYYYYYYYYYYYYYYYYYYYYY"'
        ),
        required=True
    )
    channel = schema.TextLine(
        title=_(u'Channel'),
        description=_(
            u'Channel to receive the message. eg.:"#plone-rulez"'
        ),
        required=True
    )
    pretext = schema.TextLine(
        title=_(u'Pretext'),
        description=_(
            u'This is optional text that appears above the message attachment block.'
        ),
        required=False
    )
    title = schema.TextLine(
        title=_(u'Title'),
        description=_(
            u'The title is displayed as larger, bold text near the top of a message attachment.'
        ),
        required=True
    )
    title_link = schema.TextLine(
        title=_(u'Title Link'),
        description=_('Link to be added to the title. i.e.: "${absolute_url}"'),
        default=u'${absolute_url}',
        required=False
    )
    text = schema.TextLine(
        title=_(u'Text'),
        description=_(
            u'This is the main text in a message attachment.'
        ),
        required=True
    )
    color = schema.TextLine(
        title=_(u'Color'),
        description=_(
            'Color of the message. Valid values are "good", "warning", "danger" or '
            'any hex color code (eg. #439FE0)'
        ),
        required=False
    )
    icon = schema.TextLine(
        title=_(u'Icon'),
        description=_(
            u'Icon to be displayed on the message. eg:":flag-br:"'
        ),
        required=False
    )
    username = schema.TextLine(
        title=_(u'Username'),
        description=_(
            u'Name to be displayed as the author of this message.'
        ),
        default=u'Plone CMS',
        required=True
    )
    fields = schema.Text(
        title=_(u'Fields'),
        description=_(
            u'Fields are added to the bottom of the Slack message like a small table.'
            u'Please add one definition per line in the format:"title|value|Short", i.e:'
            u'"Review State|${review_state_title}|True"'
        ),
        required=False
    )


@implementer(ISlackAction, IRuleElementData)
class SlackAction(SimpleItem):
    """The implementation of the action defined before."""

    webhook_url = SLACK_WEBHOOK_URL
    channel = u''
    pretext = u''
    title = u''
    title_link = u'${absolute_url}'
    text = u''
    color = u''
    icon = u''
    username = u''
    fields = u''

    element = 'plone.actions.Slack'

    @property
    def summary(self):
        return _(u'Post a message on channel ${channel}', mapping=dict(channel=self.channel))


@implementer(IExecutable)
@adapter(Interface, ISlackAction, Interface)
class SlackActionExecutor(object):
    """Executor for the Slack Action."""

    def __init__(self, context, element, event):
        """Initialize action executor."""
        self.context = context
        self.element = element
        self.event = event

    def _process_fields_(self, interpolator):
        """Process element.fields and return a list of dicts.

        Read more at: https://api.slack.com/docs/message-attachments

        :returns: Message attachment fields.
        :rtype: list of dictionaries.
        """
        element = self.element
        fields_spec = element.fields or ''
        fields = []
        for item in fields_spec.split('\n'):
            try:
                title, value, short = item.split('|')
            except ValueError:
                continue
            short = True if short.lower() == 'true' else False
            value = interpolator(value).strip()
            fields.append({'title': title, 'value': value, 'short': short})
        return fields

    def get_ftw_configuration(self):
        """Return the configuration parameters used by ftw.slacker.

        :returns: Configuration parameters.
        :rtype: dict.
        """
        params = {
            'webhook_url': self.element.webhook_url,
            'timeout': 10,
            'verify': True,
        }
        return params

    def get_message_payload(self):
        """Process the action and return a dictionary with the Slack message payload.

        :returns: Slack message payload.
        :rtype: dict.
        """
        obj = self.event.object
        element = self.element
        interpolator = IStringInterpolator(obj)
        title = interpolator(element.title).strip()
        title_link = interpolator(element.title_link).strip()
        pretext = interpolator(element.pretext).strip()
        text = interpolator(element.text).strip()
        color = element.color
        icon = element.icon
        channel = element.channel
        username = element.username
        payload = {
            'attachments': [
                {
                    'color': color,
                    'fallback': text,
                    'title': title,
                    'title_link': title_link,
                    'pretext': pretext,
                    'fields': self._process_fields_(interpolator)
                }
            ],
            'icon_emoji': icon,
            'text': text,
            'username': username,
            'channel': channel
        }
        return payload

    def notify_slack(self, payload):
        """Send message to Slack using ftw.slacker.notify_slack.

        :param payload: Payload to be sent to ftw.slacker.notify_slack.
        :type payload: dict
        """
        return notify_slack(**payload)

    def get_payload(self):
        """Return payload to be sent to ftw.slacker.notify_slack.

        :returns: Payload to be sent to ftw.slacker.notify_slack.
        :rtype: dict
        """
        payload = self.get_message_payload()
        payload.update(self.get_ftw_configuration())
        return payload

    def __call__(self):
        """Execute the action."""
        payload = self.get_payload()
        self.notify_slack(payload)
        return True


class SlackAddForm(ActionAddForm):
    """An add form for the Slack Action."""

    schema = ISlackAction
    label = _(u'Add Slack Action')
    description = _(u'Action to post a message to a Slack channel.')
    form_name = _(u'Configure element')
    Type = SlackAction

    # custom template will allow us to add help text
    template = ViewPageTemplateFile('slack.pt')


class SlackAddFormView(ContentRuleFormWrapper):
    """Wrapped add form for Slack Action."""

    form = SlackAddForm


class SlackEditForm(ActionEditForm):
    """An edit form for the slack action."""

    schema = ISlackAction
    label = _(u'Edit Slack Action')
    description = _(u'Action to post a message to a Slack channel.')
    form_name = _(u'Configure element')

    # custom template will allow us to add help text
    template = ViewPageTemplateFile('slack.pt')


class SlackEditFormView(ContentRuleFormWrapper):
    """Wrapped edit form for Slack Action."""

    form = SlackEditForm
