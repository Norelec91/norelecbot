#!/usr/bin/python3.6

import sys
import getopt
import asyncio
import secrets

from aiohttp import web

import telepot

import config
import game
import telegram

async def info(request):
    return web.Response(status=200, reason='OK', headers={'Content-Type': 'text/html'}, body=game.generateInfoHTML().encode('utf-8'))

async def feeder(request):
    data = await request.text()
    webhook.feed(data)

    return web.Response(body='OK'.encode('utf-8'))

async def init(app, webhook_token):
    app.router.add_route('GET', config.URL, info)
    app.router.add_route('GET', config.URL + webhook_token, feeder)
    app.router.add_route('POST', config.URL + webhook_token, feeder)

def main(argv):         
    try:
        game.disableAllRobots()
        web.run_app(app, port=config.PORT)
    except KeyboardInterrupt:
        pass

loop = asyncio.get_event_loop()
app = web.Application(loop=loop)
webhook_token = secrets.token_urlsafe()
loop.run_until_complete(init(app, webhook_token))
bot = telegram.getBot(loop)
loop.run_until_complete(telegram.init(app, bot, webhook_token))
webhook = telegram.getWebhook(bot)
loop.create_task(webhook.run_forever())
loop.create_task(telegram.messagesObserver(loop, bot))

if __name__ == "__main__":
    main(sys.argv[1:])
