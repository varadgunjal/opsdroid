"""A connector for Facebook Messenger."""
import json
import logging

import aiohttp

from opsdroid.connector import Connector
from opsdroid.message import Message


_LOGGER = logging.getLogger(__name__)
_FACEBOOK_SEND_URL = "https://graph.facebook.com/v2.6/me/messages" \
                     "?access_token={}"


class ConnectorFacebook(Connector):
    """A connector for Facebook Messenger.

    It handles the incoming messages from facebook messenger and sends the user
    messages. It also handles the authentication challenge by verifying the
    token.

    Attributes:
        config: The config for this connector specified in the
            `configuration.yaml` file.
        name: String name of the connector.
        opsdroid: opsdroid instance.
        default_room: String name of default room for chat messages.
        bot_name: String name for bot.

    """

    def __init__(self, config):
        """Connector Setup."""
        super().__init__(config)
        _LOGGER.debug("Starting facebook connector")
        self.config = config
        self.name = self.config.get("name", "facebook")
        self.opsdroid = None
        self.default_room = None
        self.bot_name = config.get("bot-name", 'opsdroid')

    async def connect(self, opsdroid):
        """Connect to the chat service."""
        self.opsdroid = opsdroid

        self.opsdroid.web_server.web_app.router.add_post(
            "/connector/{}".format(self.name),
            self.facebook_message_handler)

        self.opsdroid.web_server.web_app.router.add_get(
            "/connector/{}".format(self.name),
            self.facebook_challenge_handler)

    async def facebook_message_handler(self, request):
        """Handle incoming message.

        For each entry in request, it will check if the entry is a `messaging`
        type. Then it will process all the incoming messages.

        Return:
            A 200 OK response. The Messenger Platform will resend the webhook
            event every 20 seconds, until a 200 OK response is received.
            Failing to return a 200 OK may cause your webhook to be
            unsubscribed by the Messenger Platform.

        """
        req_data = await request.json()

        if "object" in req_data and req_data["object"] == "page":
            for entry in req_data["entry"]:
                for fb_msg in entry["messaging"]:
                    _LOGGER.debug(fb_msg)
                    try:
                        message = Message(fb_msg["message"]["text"],
                                          fb_msg["sender"]["id"],
                                          fb_msg["sender"]["id"],
                                          self)
                        await self.opsdroid.parse(message)
                    except KeyError as error:
                        _LOGGER.error(error)

        return aiohttp.web.Response(
            text=json.dumps("Received"), status=200)

    async def facebook_challenge_handler(self, request):
        """Handle auth challenge.

        Return:
            A response if challenge is a success or failure.

        """
        _LOGGER.debug(request.query)
        if request.query["hub.verify_token"] == \
                self.config.get('verify-token'):
            return aiohttp.web.Response(
                text=request.query["hub.challenge"], status=200)
        return aiohttp.web.Response(
            text=json.dumps("Bad verify token"), status=403)

    async def listen(self, opsdroid):
        """Listen for new message.

        Listening is handled by the aiohttp web server

        """

    async def respond(self, message, room=None):
        """Respond with a message."""
        _LOGGER.debug("Responding to facebook")
        url = _FACEBOOK_SEND_URL.format(self.config.get('page-access-token'))
        headers = {'content-type': 'application/json'}
        payload = {
            "recipient": {
                "id": message.room
            },
            "message": {
                "text": message.text
            }
        }
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                url,
                data=json.dumps(payload),
                headers=headers
            )
            if resp.status < 300:
                _LOGGER.info("Responded with: %s", message.text)
            else:
                _LOGGER.debug(resp.status)
                _LOGGER.debug(await resp.text())
                _LOGGER.error("Unable to respond to facebook")
