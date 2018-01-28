import os
import logging
import asyncio
import io
import datetime

from aiohttp import web

import telepot
import emoji

from telepot.aio.loop import OrderedWebhook
from telepot.aio.delegate import per_chat_id, create_open, pave_event_space

import config
import game

logger = logging.getLogger('admins_commands')
logger.setLevel(logging.INFO)
handler = logging.FileHandler('./logs/admins_commands.txt', encoding='utf-8')
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger = logging.getLogger('commands')
logger.setLevel(logging.INFO)
handler = logging.FileHandler('./logs/commands.txt', encoding='utf-8')
handler.setLevel(logging.INFO)
handler.setFormatter(formatter)
logger.addHandler(handler)

TOKEN = config.TOKEN
URL = config.URL
PORT = config.PORT
NAME = config.NAME

def registered(function):
    def wrapper(self):
        self.player = game.getPlayerByUser_id(self.user_id)

        if self.player:
            if self.player['is_banned'] == 0:
                if self.player['current_username'] != self.username:
                    game.updatePlayerCurrentUsername(self.user_id, self.username)

                return function(self)
        else:
            game.register(self.user_id, self.username)
            
            game.sendMessage(self.chat_id, '@%s, ti sei appena registrato nel bot! Fai /faq per vedere i comandi.' % (self.username))
            
            commands[self.command].setParameters(user_id=self.user_id, username=self.username, chat_type=self.chat_type, chat_id=self.chat_id, parameters=self.parameters)
            commands[self.command].execute()

    return wrapper

def owner(function):
    def wrapper(self):
        if self.player['is_owner'] == 1:
            return function(self)
    return wrapper

def admin(function):
    def wrapper(self):
        if self.player['is_admin'] == 1:
            acl = logging.getLogger('admins_commands')
            acl.info('%s: %s %s' % (self.username, self.command, str(self.parameters)))

            return function(self)
    return wrapper

def private(function):
    def wrapper(self):
        if self.chat_type == 'private':
            return function(self)
        else:
            game.sendMessage(self.chat_id, '@%s, in privato.' % (self.username))
    return wrapper

class Command():
    def setParameters(self, **kwargs):
        self.player = {}
        self.user_id = kwargs['user_id']
        self.username = kwargs['username']
        self.chat_type = kwargs['chat_type']
        self.chat_id = kwargs['chat_id']
        self.parameters = kwargs['parameters']

class StartCommand(Command):
    @private
    @registered
    def execute(self):
        commands['/faq'].setParameters(user_id=self.user_id, username=self.username, chat_type=self.chat_type, chat_id=self.chat_id, parameters=self.parameters)
        commands['/faq'].execute()

class FAQCommand(Command):
    @private
    @registered
    def execute(self):
        with open('faq.txt', encoding='utf-8') as f:
            faq_str = f.read()

        game.sendMessage(self.chat_id, emoji.emojize(faq_str, use_aliases=True))

class MineCommand(Command):
    #@private
    @registered
    def execute(self):
        try:
            ball_type = game.playerMine(self.user_id)

            if ball_type == 'Ball':
                ball_str = ''
            elif ball_type == 'NorelecBall':
                ball_str = 'Scopri che una è di Norelec 🍆 e la vendi per 100 palle. '
            elif ball_type == 'GoldBall':
                ball_str = 'Scopri che una è d\'oro 🍋 e la vendi per 50 palle. '
            elif ball_type == 'ArgentBall':
                ball_str = 'Scopri che una è d\'argento 🍐 e la vendi per 20 palle. '
            elif ball_type == 'BronzeBall':
                ball_str = 'Scopri che una è di bronzo 🍊 e la vendi per 10 palle. '
            elif ball_type == 'WoodenBall':
                ball_str = 'Scopri che una è di legno 🌰 e la vendi per 5 palle. '
            elif ball_type == 'BrokenBall':
                ball_str = 'Ma scopri che una è di neve ❄️ e ti si scioglie in mano. '
            elif ball_type == 'EvilBall':
                ball_str = 'Ma scopri che una è cattiva 😈 e ti mangia 10 palle dal contenitore. '
            elif ball_type == 'ExplosiveBall':
                ball_str = 'Ma scopri che una è esplosiva 💥 e ti rompe 20 palle dal contenitore. '
            elif ball_type == 'DoronzoBall':
                ball_str = 'Ma scopri che una è di Doronzo 🥕 e ti fa cadere 100 palle dal contenitore. '

            player = game.getPlayerByUser_id(self.user_id)

            if game.getHandsFormula(player['hands_level']) == 1:
                ball_countable_str = 'palla'
            else:
                ball_countable_str = 'palle'

            game.sendMessage(self.chat_id, '@%s, hai raccolto %d %s! %sOra ne hai in tutto %d e ne mancano %d da raccogliere nel castello. %s' % (player['username'], game.getHandsFormula(player['hands_level']), ball_countable_str, ball_str, player['balls'], game.getGameState()['units'], game.getRandomQuote()))
        except game.BoxFullException as e:
                game.sendMessage(self.chat_id, '@%s, hai il contenitore pieno, fallo salire di livello con /aggiornacontenitore!' % (self.username))
        except game.CooldownException as e:
            if e.minutes == 0:
                minutes_str = ''
            elif e.minutes == 1:
                if e.seconds == 0:
                    minutes_str = '1 minuto '
                else:
                    minutes_str = '1 minuto e '
            else:
                if e.seconds == 0:
                    minutes_str = '%d minuti ' % (e.minutes)
                else:
                    minutes_str = '%d minuti e ' % (e.minutes)

            if e.seconds == 0:
                seconds_str = ''
            elif e.seconds == 1:
                seconds_str = '1 secondo'
            else:
                seconds_str = '%d secondi' % (e.seconds)

            game.sendMessage(self.chat_id, '@%s, devi aspettare %s%s prima di poter raccogliere di nuovo.' % (self.username, minutes_str, seconds_str))
        except game.ExhaustedMineException:
            game.sendMessage(self.chat_id, '@%s, sono finite le palle nel castello!' % (self.username))

class HandsUpgradeCommand(Command):
    #@private
    @registered
    def execute(self):
        try:
            game.handsUpgrade(self.user_id)
            game.sendMessage(self.chat_id, '@%s, le tue mani salgono di livello %d. Ora puoi raccogliere %d palle.' % (self.username, self.player['hands_level'] + 1, game.getHandsFormula(self.player['hands_level'] + 1)))
        except game.NotEnoughBallsException as e:
            game.sendMessage(self.chat_id, '@%s, ti servono ancora %d palle per poter far avanzare di livello le tue mani.' % (self.username, e.diff))

class FeetUpgradeCommand(Command):
    #@private
    @registered
    def execute(self):
        try:
            game.feetUpgrade(self.user_id)

            seconds = game.DELAY_TIME - game.getFeetFormula(self.player['feet_level'] + 1)
            hours, r = divmod(seconds, 3600)
            minutes, seconds = divmod(r, 60)

            if minutes == 0:
                minutes_str = ''
            elif minutes == 1:
                if seconds == 0:
                    minutes_str = '1 minuto '
                else:
                    minutes_str = '1 minuto e '
            else:
                if seconds == 0:
                    minutes_str = '%d minuti ' % (minutes)
                else:
                    minutes_str = '%d minuti e ' % (minutes)

            if seconds == 0:
                seconds_str = ''
            elif seconds == 1:
                seconds_str = '1 secondo'
            else:
                seconds_str = '%d secondi' % (seconds)

            game.sendMessage(self.chat_id, '@%s, i tuoi piedi salgono di livello %d. Ora tra una raccolta e l\'altra attendi %s%s.' % (self.username, self.player['feet_level'] + 1, minutes_str, seconds_str))
        except game.NotEnoughBallsException as e:
            game.sendMessage(self.chat_id, '@%s, ti servono ancora %d palle per poter far avanzare di livello i tuoi piedi.' % (self.username, e.diff))
        except game.LevelCapException:
            game.sendMessage(self.chat_id, '@%s, non puoi aggiornare oltre questo livello.' % (self.username))

class BoxUpgradeCommand(Command):
    #@private
    @registered
    def execute(self):
        try:
            game.boxUpgrade(self.user_id)

            game.sendMessage(self.chat_id, '@%s, il tuo contenitore sale di livello %d. Ora può contenere %d palle.' % (self.username, self.player['box_level'] + 1, game.getBoxFormula(self.player['box_level'] + 1)))
        except game.NotEnoughBallsException as e:
            game.sendMessage(self.chat_id, '@%s, ti servono ancora %d palle per poter far avanzare di livello il tuo contenitore.' % (self.username, e.diff))

class BuyRobotCommand(Command):
    @private
    @registered
    def execute(self):
        try:
            game.buyRobot(self.user_id)

            game.sendMessage(self.chat_id, '@%s, palla dopo palla ti senti affaticato, ti siedi sopra una panca e realizzi che la quantità di palle è davvero abnorme. Ma un\'improvvisa folata di vento ti attacca un volantino in faccia, un po\' infastidito te lo levi e per curiosità gli dai un\'occhiata: \"OFFERTISSIME DAL BARONE MERENNO93, ROBOT A SOLI 250 PALLE!\"\nNe compri subito uno.' % (self.username))
        except game.NotEnoughBallsException as e:
            game.sendMessage(self.chat_id, '@%s, ti servono ancora %d palle per poter comprare un robot.' % (self.username, e.diff))
        except game.RobotAlreadyBoughtException:
            game.sendMessage(self.chat_id, '@%s, hai già comprato un robot.' % (self.username))

class LoaderUpgradeCommand(Command):
    #@private
    @registered
    def execute(self):
        try:
            game.loaderUpgrade(self.user_id)

            game.sendMessage(self.chat_id, '@%s, la pala caricatrice del tuo robot sale di livello %d. Ora può raccogliere per te %d palle.' % (self.username, self.player['loader_level'] + 1, game.getLoaderFormula(self.player['loader_level'] + 1)))
        except game.NotEnoughBallsException as e:
            game.sendMessage(self.chat_id, '@%s, ti servono ancora %d palle per poter far avanzare di livello la pala caricatrice del tuo robot.' % (self.username, e.diff))
        except game.RobotNotBoughtException as e:
            game.sendMessage(self.chat_id, '@%s, devi prima comprare un robot con /comprarobot.' % (self.username))

class TracksUpgradeCommand(Command):
    #@private
    @registered
    def execute(self):
        try:
            game.tracksUpgrade(self.user_id)

            seconds = game.ROBOT_DELAY_TIME - game.getTracksFormula(self.player['tracks_level'] + 1)
            hours, r = divmod(seconds, 3600)
            minutes, seconds = divmod(r, 60)

            if minutes == 0:
                minutes_str = ''
            elif minutes == 1:
                if seconds == 0:
                    minutes_str = '1 minuto '
                else:
                    minutes_str = '1 minuto e '
            else:
                if seconds == 0:
                    minutes_str = '%d minuti ' % (minutes)
                else:
                    minutes_str = '%d minuti e ' % (minutes)

            if seconds == 0:
                seconds_str = ''
            elif seconds == 1:
                seconds_str = '1 secondo'
            else:
                seconds_str = '%d secondi' % (seconds)

            game.sendMessage(self.chat_id, '@%s, i cingoli del tuo robot salgono di livello %d. Ora tra una raccolta e l\'altra attende %s%s.' % (self.username, self.player['tracks_level'] + 1, minutes_str, seconds_str))
        except game.NotEnoughBallsException as e:
            game.sendMessage(self.chat_id, '@%s, ti servono ancora %d palle per poter far avanzare di livello i cingoli del tuo robot.' % (self.username, e.diff))
        except game.RobotNotBoughtException as e:
            game.sendMessage(self.chat_id, '@%s, devi prima comprare un robot con /comprarobot.' % (self.username))
        except game.LevelCapException:
            game.sendMessage(self.chat_id, '@%s, non puoi aggiornare oltre questo livello.' % (self.username))

class EnableRobotCommand(Command):
    @private
    @registered
    def execute(self):
        try:
            game.enableRobot(self.user_id)
            
            game.sendMessage(self.chat_id, '@%s, il tuo robot si è acceso.' % (self.username))
            #game.sendMessage(self.chat_id, 'Il tuo robot sembra non accendersi più a causa di una grossa interferenza dalla connessione Internet satellitare di Norelec per guardare i pornazzi in 16K.')
        except game.RobotNotBoughtException:
            game.sendMessage(self.chat_id, '@%s, devi prima comprare un robot con /comprarobot.' % (self.username))

class DisableRobotCommand(Command):
    @private
    @registered
    def execute(self):
        try:
            game.disableRobot(self.user_id)
        except game.RobotNotBoughtException:
            game.sendMessage(self.chat_id, '@%s, devi prima comprare un robot con /comprarobot.' % (self.username))

class EnableRobotMessagesCommand(Command):
    @private
    @registered
    def execute(self):
        game.enableRobotMessages(self.user_id)
        game.sendMessage(self.chat_id, '@%s, messaggi robot attivati.' % (self.username))

class DisableRobotMessagesCommand(Command):
    @private
    @registered
    def execute(self):
        game.disableRobotMessages(self.user_id)
        game.sendMessage(self.chat_id, '@%s, messaggi robot disattivati.' % (self.username))

class InfoCommand(Command):
    @registered
    def execute(self):
        if len(self.parameters) == 0:
            gamestate = game.getGameState()

            game.sendMessage(self.chat_id, 'Ultima palla raccolta da @%s alle %s. Mancano %d palle da raccogliere.' % (gamestate['last_miner'], gamestate['last_mine_time'].strftime(game.ITALIAN_FMT), gamestate['units']))
        else:
            player = game.getPlayerByCurrentUsername(self.parameters[0].replace('@', ''))

            if player:
                if player['is_banned'] == 1:
                    game.sendMessage(self.chat_id, 'Il giocatore @%s (%d) è stato bannato per la seguente motivazione: %s' % (player['username'], player['user_id'], player['ban_reason']))
                else:
                    if player['last_mine_time']:
                        last_mine_time = 'ed ha raccolto l\'ultima alle '+ str(player['last_mine_time'].strftime(game.ITALIAN_FMT))
                    else:
                        last_mine_time = ''

                    if player['balls'] == 0:
                        balls = 'non ha palle'
                    elif player['balls'] == 1:
                        balls = 'ha 1 palla'
                    else:
                        balls = 'ha ' + str(player['balls']) + ' palle'

                    stat_str = 'Il giocatore @%s (%d) %s %s.\n\nLe sue mani sono di livello %d, i suoi piedi sono di livello %d ed il suo contenitore è di livello %d.' % (player['username'], player['user_id'], balls, last_mine_time, player['hands_level'], player['feet_level'], player['box_level'])
                    
                    if player['loader_level'] and player['tracks_level'] > 0:
                        if player['is_robot_enabled']:
                            is_robot_enabled = 'ACCESO'
                        else:
                            is_robot_enabled = 'SPENTO'

                        stat_str = stat_str + '\n\nIl suo robot ha la pala caricatrice di livello %d, i cingoli di livello %d ed è %s.' % (player['loader_level'], player['tracks_level'], is_robot_enabled)

                    if player['gold_hamcha'] > 0:
                        stat_str = stat_str + '\n\nHa vinto %d Hamcha d\'Oro 🏅!' % (player['gold_hamcha'])

                    titles = game.getPlayerTitles(player['user_id'])

                    if titles:
                        titles_str = 'Ha i seguenti titoli:\n\n'

                        for title in titles:
                            titles_str = titles_str + '- ' + title['text'] + '\n\tassegnato il ' + str(title['date'].strftime(game.ITALIAN_FMT)) + '\n'

                        stat_str = stat_str + '\n\n' + titles_str

                    game.sendMessage(self.chat_id, stat_str)
            else:
                game.sendMessage(self.chat_id, 'Il giocatore @%s non è registrato.' % (self.parameters[0].replace('@', '')))

class MeCommand(Command):
    @registered
    def execute(self):
        self.parameters = [self.username]
        commands['/info'].setParameters(user_id=self.user_id, username=self.username, chat_type=self.chat_type, chat_id=self.chat_id, parameters=self.parameters)
        commands['/info'].execute()

class LinkCommand(Command):
    @registered
    def execute(self):
        game.sendMessage(self.chat_id, 'http://%s%s' % (config.DOMAIN, config.URL))

class GetQuotesCommand(Command):
    @private
    @registered
    @owner
    def execute(self):
        file = open('./quotes.txt', 'w', encoding='utf-8')
        file.write(str(game.getQuotes()).replace('(', '').replace(')', '').replace('}, ', '}\n'))
        file.close()
        game.sendFile(self.chat_id, open('./quotes.txt', 'rb'))

class AddHandsCommand(Command):
    @registered
    @owner
    def execute(self):
        if len(self.parameters) > 0:
            if len(self.parameters) != 0:
                if self.parameters[0].isdigit():
                    player = game.getPlayerByUser_id(self.parameters[0])
                else:
                    player = game.getPlayerByCurrentUsername(self.parameters[0].replace('@', ''))

                if player:
                    hands_inc = int(self.parameters[1])

                    game.addHandsLevel(player['user_id'], hands_inc)

                    game.sendMessage(self.chat_id, 'Il giocatore @%s ora ha le mani di livello %d.' % (player['username'], player['hands_level'] + hands_inc))
                else:
                    game.sendMessage(self.chat_id, 'Il giocatore @%s non è registrato.' % (player['username']))
            else:
                game.sendMessage(self.chat_id, 'Di quanto vuoi incrementare il livello delle mani?')
        else:
            game.sendMessage(self.chat_id, 'A chi vuoi incrementare il livello delle mani?')

class DelHandsCommand(Command):
    @registered
    @owner
    def execute(self):
        if len(self.parameters) > 0:
            if len(self.parameters) != 0:
                if self.parameters[0].isdigit():
                    player = game.getPlayerByUser_id(self.parameters[0])
                else:
                    player = game.getPlayerByCurrentUsername(self.parameters[0].replace('@', ''))

                if player:
                    hands_dec = int(self.parameters[1])

                    if hands_dec <= player['hands_level']:
                        game.delHandsLevel(player['user_id'], hands_dec)

                        game.sendMessage(self.chat_id, 'Il giocatore @%s ora ha le mani di livello %d.' % (player['username'], player['hands_level'] - hands_dec))
                    else:
                        game.sendMessage(self.chat_id, 'Valore troppo piccolo.')
                else:
                    game.sendMessage(self.chat_id, 'Il giocatore @%s non è registrato.' % (self.parameters[0].replace('@', '')))
            else:
                game.sendMessage(self.chat_id, 'Di quanto vuoi decrementare il livello delle mani?')
        else:
            game.sendMessage(self.chat_id, 'A chi vuoi decrementare il livello delle mani?')

class AddFeetCommand(Command):
    @registered
    @owner
    def execute(self):
        if len(self.parameters) > 0:
            if len(self.parameters) != 0:
                if self.parameters[0].isdigit():
                    player = game.getPlayerByUser_id(self.parameters[0])
                else:
                    player = game.getPlayerByCurrentUsername(self.parameters[0].replace('@', ''))

                if player:
                    feet_inc = int(self.parameters[1])

                    game.addFeetLevel(player['user_id'], feet_inc)

                    game.sendMessage(self.chat_id, 'Il giocatore @%s ora ha i piedi di livello %d.' % (player['username'], player['feet_level'] + feet_inc))
                else:
                    game.sendMessage(self.chat_id, 'Il giocatore @%s non è registrato.' % (self.parameters[0].replace('@', '')))
            else:
                game.sendMessage(self.chat_id, 'Di quanto vuoi incrementare il livello dei piedi?')
        else:
            game.sendMessage(self.chat_id, 'A chi vuoi incrementare il livello dei piedi?')

class DelFeetCommand(Command):
    @registered
    @owner
    def execute(self):
        if len(self.parameters) > 0:
            if len(self.parameters) != 0:
                if self.parameters[0].isdigit():
                    player = game.getPlayerByUser_id(self.parameters[0])
                else:
                    player = game.getPlayerByCurrentUsername(self.parameters[0].replace('@', ''))

                if player:
                    feet_dec = int(self.parameters[1])

                    if feet_dec <= player['feet_level']:
                        game.delFeetLevel(player['user_id'], int(self.parameters[1]))

                        game.sendMessage(self.chat_id, 'Il giocatore @%s ora ha i piedi di livello %d.' % (player['username'], player['feet_level'] - int(self.parameters[1])))
                    else:
                        game.sendMessage(self.chat_id, 'Valore troppo piccolo.')
                else:
                    game.sendMessage(self.chat_id, 'Il giocatore @%s non è registrato.' % (self.parameters[0].replace('@', '')))
            else:
                game.sendMessage(self.chat_id, 'Di quanto vuoi decrementare il livello dei piedi?')
        else:
            game.sendMessage(self.chat_id, 'A chi vuoi decrementare il livello dei piedi?')

class AddBoxCommand(Command):
    @registered
    @owner
    def execute(self):
        if len(self.parameters) > 0:
            if len(self.parameters) != 0:
                if self.parameters[0].isdigit():
                    player = game.getPlayerByUser_id(self.parameters[0])
                else:
                    player = game.getPlayerByCurrentUsername(self.parameters[0].replace('@', ''))

                if player:
                    box_inc = int(self.parameters[1])

                    game.addBoxLevel(player['user_id'], box_inc)

                    game.sendMessage(self.chat_id, 'Il giocatore @%s ora ha il contenitore di livello %d.' % (player['username'], player['box_level'] + box_inc))
                else:
                    game.sendMessage(self.chat_id, 'Il giocatore @%s non è registrato.' % (self.parameters[0].replace('@', '')))
            else:
                game.sendMessage(self.chat_id, 'Di quanto vuoi incrementare il livello del contenitore?')
        else:
            game.sendMessage(self.chat_id, 'A chi vuoi incrementare il livello del contenitore?')

class DelBoxCommand(Command):
    @registered
    @owner
    def execute(self):
        if len(self.parameters) > 0:
            if len(self.parameters) != 0:
                if self.parameters[0].isdigit():
                    player = game.getPlayerByUser_id(self.parameters[0])
                else:
                    player = game.getPlayerByCurrentUsername(self.parameters[0].replace('@', ''))

                if player:
                    box_dec = int(self.parameters[1])

                    if box_dec <= player['box_level']:
                        game.delBoxLevel(player['user_id'], box_dec)

                        game.sendMessage(self.chat_id, 'Il giocatore @%s ora ha il contenitore di livello %d.' % (player['username'], player['box_level'] - box_dec))
                    else:
                        game.sendMessage(self.chat_id, 'Valore troppo piccolo.')
                else:
                    game.sendMessage(self.chat_id, 'Il giocatore @%s non è registrato.' % (self.parameters[0].replace('@', '')))
            else:
                game.sendMessage(self.chat_id, 'Di quanto vuoi decrementare il livello del contenitore?')
        else:
            game.sendMessage(self.chat_id, 'A chi vuoi decrementare il livello del contenitore?')

class AddLoaderCommand(Command):
    @registered
    @owner
    def execute(self):
        if len(self.parameters) > 0:
            if len(self.parameters) != 0:
                if self.parameters[0].isdigit():
                    player = game.getPlayerByUser_id(self.parameters[0])
                else:
                    player = game.getPlayerByCurrentUsername(self.parameters[0].replace('@', ''))

                if player:
                    loader_inc = int(self.parameters[1])

                    game.addLoaderLevel(player['user_id'], loader_inc)

                    game.sendMessage(self.chat_id, 'Il giocatore @%s ora ha le pala caricatrice di livello %d.' % (player['username'], player['loader_level'] + loader_inc))
                else:
                    game.sendMessage(self.chat_id, 'Il giocatore @%s non è registrato.' % (self.parameters[0].replace('@', '')))
            else:
                game.sendMessage(self.chat_id, 'Di quanto vuoi incrementare il livello della pala caricatrice?')
        else:
            game.sendMessage(self.chat_id, 'A chi vuoi incrementare il livello della pala caricatrice?')

class DelLoaderCommand(Command):
    @registered
    @owner
    def execute(self):
        if len(self.parameters) > 0:
            if len(self.parameters) != 0:
                if self.parameters[0].isdigit():
                    player = game.getPlayerByUser_id(self.parameters[0])
                else:
                    player = game.getPlayerByCurrentUsername(self.parameters[0].replace('@', ''))

                if player:
                    loader_dec = int(self.parameters[1])

                    if loader_dec <= player['loader_level']:
                        game.delLoaderLevel(player['user_id'], loader_dec)

                        game.sendMessage(self.chat_id, 'Il giocatore @%s ora ha la pala caricatrice di livello %d.' % (player['username'], player['loader_level'] - loader_dec))
                    else:
                        game.sendMessage(self.chat_id, 'Valore troppo basso.')
                else:
                    game.sendMessage(self.chat_id, 'Il giocatore @%s non è registrato.' % (self.parameters[0].replace('@', '')))
            else:
                game.sendMessage(self.chat_id, 'Di quanto vuoi decrementare il livello della pala caricatrice?')
        else:
            game.sendMessage(self.chat_id, 'A chi vuoi decrementare il livello della pala caricatrice?')

class AddTracksCommand(Command):
    @registered
    @owner
    def execute(self):
        if len(self.parameters) > 0:
            if len(self.parameters) != 0:
                if self.parameters[0].isdigit():
                    player = game.getPlayerByUser_id(self.parameters[0])
                else:
                    player = game.getPlayerByCurrentUsername(self.parameters[0].replace('@', ''))

                if player:
                    tracks_inc = int(self.parameters[1])

                    game.addTracksLevel(player['user_id'], tracks_inc)

                    game.sendMessage(self.chat_id, 'Il giocatore @%s ora ha i cingoli del robot di livello %d.' % (player['username'], player['tracks_level'] + tracks_inc))
                else:
                    game.sendMessage(self.chat_id, 'Il giocatore @%s non è registrato.' % (self.parameters[0].replace('@', '')))
            else:
                game.sendMessage(self.chat_id, 'Di quanto vuoi incrementare il livello dei cingoli del robot?')
        else:
            game.sendMessage(self.chat_id, 'A chi vuoi incrementare il livello dei cingoli del robot?')

class DelTracksCommand(Command):
    @registered
    @owner
    def execute(self):
        if len(self.parameters) > 0:
            if len(self.parameters) != 0:
                if self.parameters[0].isdigit():
                    player = game.getPlayerByUser_id(self.parameters[0])
                else:
                    player = game.getPlayerByCurrentUsername(self.parameters[0].replace('@', ''))

                if player:
                    tracks_dec = int(self.parameters[1])

                    if tracks_dec <= player['tracks_level']:
                        game.delTracksLevel(player['user_id'], tracks_dec)

                        game.sendMessage(self.chat_id, 'Il giocatore @%s ora ha i cingoli del robot di livello %d.' % (player['username'], player['tracks_level'] - tracks_dec))
                    else:
                        game.sendMessage(self.chat_id, 'Valore troppo basso.')
                else:
                    game.sendMessage(self.chat_id, 'Il giocatore @%s non è registrato.' % (self.parameters[0].replace('@', '')))
            else:
                game.sendMessage(self.chat_id, 'Di quanto vuoi decrementare il livello dei cingoli del robot?')
        else:
            game.sendMessage(self.chat_id, 'A chi vuoi decrementare il livello dei cingoli del robot?')

class AddTitleCommand(Command):
    @registered
    @owner
    def execute(self):
        if len(self.parameters) > 0:
            if len(self.parameters) != 0:
                if self.parameters[0].isdigit():
                    player = game.getPlayerByUser_id(self.parameters[0])
                else:
                    player = game.getPlayerByCurrentUsername(self.parameters[0].replace('@', ''))

                if player:
                    title = ' '.join(self.parameters[1:])

                    game.addTitle(player['user_id'], title)

                    game.sendMessage(self.chat_id, 'Ho aggiunto il seguente titolo: %s' % (title))
                else:
                    game.sendMessage(self.chat_id, 'Il giocatore @%s non è registrato.' % (self.parameters[0].replace('@', '')))
            else:
                game.sendMessage(self.chat_id, 'Che titolo vuoi mettere?')
        else:
            game.sendMessage(self.chat_id, 'A chi vuoi mettere il titolo?')

class DelTitleCommand(Command):
    @registered
    @owner
    def execute(self):
        if len(self.parameters) > 0:
            if len(self.parameters) != 0:
                if self.parameters[0].isdigit():
                    player = game.getPlayerByUser_id(self.parameters[0])
                else:
                    player = game.getPlayerByCurrentUsername(self.parameters[0].replace('@', ''))

                if player:
                    title = ' '.join(self.parameters[1:])

                    game.delTitle(player['user_id'], title)

                    game.sendMessage(self.chat_id, 'Ho eliminato il seguente titolo: %s' % (title))
                else:
                    game.sendMessage(self.chat_id, 'Il giocatore @%s non è registrato.' % (self.parameters[0].replace('@', '')))
            else:
                game.sendMessage(self.chat_id, 'Che titolo vuoi levare?')
        else:
            game.sendMessage(self.chat_id, 'A chi vuoi levare il titolo?')

class AddGoldHamchaCommand(Command):
    @registered
    @owner
    def execute(self):
        if len(self.parameters) > 0:
            if len(self.parameters) != 0:
                if self.parameters[0].isdigit():
                    player = game.getPlayerByUser_id(self.parameters[0])
                else:
                    player = game.getPlayerByCurrentUsername(self.parameters[0].replace('@', ''))

                if player:
                    gold_hamcha_inc = int(self.parameters[1])

                    game.addGoldHamcha(player['user_id'], gold_hamcha_inc)

                    game.sendMessage(self.chat_id, 'Il giocatore @%s ora ha %d Hamcha d\'Oro.' % (player['username'], player['gold_hamcha'] + gold_hamcha_inc))
                else:
                    game.sendMessage(self.chat_id, 'Il giocatore @%s non è registrato.' % (self.parameters[0].replace('@', '')))
            else:
                game.sendMessage(self.chat_id, 'Di quanto vuoi incrementare il numero di Hamcha d\'Oro?')
        else:
            game.sendMessage(self.chat_id, 'A chi vuoi incrementare il numero di Hamcha d\'Oro?')

class DelGoldHamchaCommand(Command):
    @registered
    @owner
    def execute(self):
        if len(self.parameters) > 0:
            if len(self.parameters) != 0:
                if self.parameters[0].isdigit():
                    player = game.getPlayerByUser_id(self.parameters[0])
                else:
                    player = game.getPlayerByCurrentUsername(self.parameters[0].replace('@', ''))

                if player:
                    gold_hamcha_dec = int(self.parameters[1])

                    if gold_hamcha_dec <= player['gold_hamcha']:
                        game.delGoldHamcha(player['user_id'], int(self.parameters[1]))

                        game.sendMessage(self.chat_id, 'Il giocatore @%s ora ha %d Hamcha d\'Oro.' % (player['username'], player['gold_hamcha'] - int(self.parameters[1])))
                    else:
                        game.sendMessage(self.chat_id, 'Valore troppo basso.')
                else:
                    game.sendMessage(self.chat_id, 'Il giocatore @%s non è registrato.' % (self.parameters[0].replace('@', '')))
            else:
                game.sendMessage(self.chat_id, 'Di quanto vuoi decrementare il numero di Hamcha d\'Oro?')
        else:
            game.sendMessage(self.chat_id, 'A chi vuoi decrementare il numero di Hamcha d\'Oro?')

class AddQuoteCommand(Command):
    @registered
    @owner
    def execute(self):
        if len(self.parameters) > 0:
            quote = ' '.join(self.parameters[0:])

            game.addQuote(quote)

            game.sendMessage(self.chat_id, 'Hai aggiunto questa citazione: %s' % (quote))
        else:
            game.sendMessage(self.chat_id, 'Che citazione vuoi aggiungere?')

class DelQuoteCommand(Command):
    @registered
    @owner
    def execute(self):
        if len(self.parameters) > 0:
            quote = ' '.join(self.parameters[0:])

            game.delQuote(quote)

            game.sendMessage(self.chat_id, 'Hai eliminato questa citazione: %s' % (quote))
        else:
            game.sendMessage(self.chat_id, 'Che citazione vuoi eliminare?')

class AddBallsCommand(Command):
    pass

class DelBallsCommand(Command):
    pass

class AddAdminCommand(Command):
    @registered
    @owner
    def execute(self):
        if len(self.parameters) > 0:
            if self.parameters[0].isdigit():
                player = game.getPlayerByUser_id(self.parameters[0])
            else:
                player = game.getPlayerByCurrentUsername(self.parameters[0].replace('@', ''))

            if player:
                game.addAdmin(player['user_id'])

                game.sendMessage(self.chat_id, 'Il giocatore @%s è admin.' % (player['username']))
            else:
                game.sendMessage(self.chat_id, 'Il giocatore @%s non è registrato.' % (player['username']))
        else:
            game.sendMessage(self.chat_id, 'Chi vuoi rendere admin?')

class DelAdminCommand(Command):
    @registered
    @owner
    def execute(self):
        if len(self.parameters) > 0:
            if self.parameters[0].isdigit():
                player = game.getPlayerByUser_id(self.parameters[0])
            else:
                player = game.getPlayerByCurrentUsername(self.parameters[0].replace('@', ''))

            if player:
                game.delAdmin(player['user_id'])

                game.sendMessage(self.chat_id, 'Il giocatore @%s non è più admin.' % (player['username']))
            else:
                game.sendMessage(self.chat_id, 'Il giocatore @%s non è registrato.' % (player['username']))
        else:
            game.sendMessage(self.chat_id, 'Chi vuoi eliminare come admin?')

class SendCommand(Command):
    @registered
    @admin
    def execute(self):
        if len(self.parameters) != 0:
            if len(self.parameters) > 1:
                if self.parameters[0].isdigit():
                    player = game.getPlayerByUser_id(self.parameters[0])
                else:
                    player = game.getPlayerByCurrentUsername(self.parameters[0].replace('@', ''))

                message = ' '.join(self.parameters[1:])

                if player:
                    game.sendMessage(player['user_id'], 'L\'admin @%s ti ha inviato il seguente messaggio: %s' % (self.player['current_username'], message))
                    game.sendMessage(self.chat_id, 'Ho inviato a @%s il seguente messaggio: %s' % (player['current_username'], message))
                else:
                    game.sendMessage(self.chat_id, 'Il giocatore @%s non è registrato.' % (self.user_id))
            else:
                game.sendMessage(self.chat_id, 'Che messaggio vuoi mandare?')
        else:
            game.sendMessage(self.chat_id, 'A chi vuoi mandare il messaggio?')

class SendAllCommand(Command):
    @registered
    @owner
    def execute(self):
        if None:
            if len(self.parameters) > 0:
                message = ' '.join(self.parameters[0:])

                game.sendMessageAll('Messaggio per tutti: ' + message)
                game.sendMessage(self.chat_id, 'Messaggio inviato.')
            else:
                game.sendMessage(self.chat_id, 'Che messaggio vuoi mandare?')
        
        game.sendMessage(self.chat_id, 'Comando disabilitato.')

class BanCommand(Command):
    @registered
    @admin
    def execute(self):
        if len(self.parameters) != 0:
            if len(self.parameters) > 1:
                if self.parameters[0].isdigit():
                    player = game.getPlayerByUser_id(self.parameters[0])
                else:
                    player = game.getPlayerByCurrentUsername(self.parameters[0].replace('@', ''))

                ban_reason = ' '.join(self.parameters[1:])

                if player:
                    if player['is_admin'] == 0:
                        game.ban(player['user_id'], ban_reason)
                        game.sendMessage(self.chat_id, 'Il giocatore @%s (%d) è stato bannato.' % (player['username'], player['user_id']))
                        game.sendMessage(player['user_id'], 'Sei stato bannato per: %s' % ban_reason)
                    else:
                        game.sendMessage(self.chat_id, 'Non puoi bannare gli admin!')
                else:
                    game.sendMessage(self.chat_id, 'Il giocatore @%s non è registrato.' % (self.user_id))
            else:
                game.sendMessage(self.chat_id, 'Perché lo vuoi bannare?')

class UnbanCommand(Command):
    @registered
    @admin
    def execute(self):
        if len(self.parameters) > 0:
            if self.parameters[0].isdigit():
                player = game.getPlayerByUser_id(self.parameters[0])
            else:
                player = game.getPlayerByCurrentUsername(self.parameters[0].replace('@', ''))

            if player:
                game.unban(player['user_id'])
                game.sendMessage(self.chat_id, 'Il giocatore @%s (%d) è stato sbannato.' % (player['username'], player['user_id']))
                game.sendMessage(player['user_id'], 'Sei stato sbannato!')
            else:
                game.sendMessage(self.chat_id, 'Il giocatore @%s non è registrato.' % (self.user_id))
        else:
            game.sendMessage(self.chat_id, 'Chi vuoi sbannare?')

class FammiVincereCommand(Command):
    @registered
    @private
    def execute(self):
        game.sendMessage(self.chat_id, 'https://tinyurl.com/2fcpre6')

commands = {
    '/start': StartCommand(),
    '/faq': FAQCommand(),
    '/raccogli': MineCommand(),
    '/aggiornamani': HandsUpgradeCommand(),
    '/aggiornapiedi': FeetUpgradeCommand(),
    '/aggiornapala': LoaderUpgradeCommand(),
    '/aggiornacingoli': TracksUpgradeCommand(),
    '/aggiornacontenitore': BoxUpgradeCommand(),
    '/comprarobot': BuyRobotCommand(),
    '/accendirobot': EnableRobotCommand(),
    '/spegnirobot': DisableRobotCommand(),
    '/attivamessaggirobot': EnableRobotMessagesCommand(),
    '/disattivamessaggirobot': DisableRobotMessagesCommand(),
    '/info': InfoCommand(),
    '/me': MeCommand(),
    '/link': LinkCommand(),
    '/getquotes': GetQuotesCommand(),
    '/addquote': AddQuoteCommand(),
    '/delquote': DelQuoteCommand(),
    '/addballs': AddBallsCommand(),
    '/delballs': DelBallsCommand(),
    '/addhands': AddHandsCommand(),
    '/delhands': DelHandsCommand(),
    '/addfeet': AddFeetCommand(),
    '/delfeet': DelFeetCommand(),
    '/addbox': AddBoxCommand(),
    '/delbox': DelBoxCommand(),
    '/addloader': AddLoaderCommand(),
    '/delloader': DelLoaderCommand(),
    '/addtracks': AddTracksCommand(),
    '/deltracks': DelTracksCommand(),
    '/addtitle': AddTitleCommand(),
    '/deltitle': DelTitleCommand(),
    '/addgoldhamcha': AddGoldHamchaCommand(),
    '/delgoldhamcha': DelGoldHamchaCommand(),
    '/addadmin': AddAdminCommand(),
    '/deladmin': DelAdminCommand(),
    '/send': SendCommand(),
    '/sendall': SendAllCommand(),
    '/ban': BanCommand(),
    '/unban': UnbanCommand(),
    '/fammivincere': FammiVincereCommand()
}

class TelegramParser(telepot.aio.helper.ChatHandler):
    def __init__(self, *args, **kwargs):
        super(TelegramParser, self).__init__(*args, **kwargs)

    async def on_chat_message(self, msg):        
        content_type, chat_type, chat_id = telepot.glance(msg)
        user_id = msg['from']['id']
        username = msg['from']['username']

        if content_type == 'text':
            tokenized_message = msg['text'].split(' ')

            cmd = tokenized_message[0]
            params = tokenized_message[1:]

            try:
                if '@' in cmd:
                    tokenized_command = cmd.split('@')
                    
                    if tokenized_command[1] == NAME:
                        cmd = tokenized_command[0]

                commands_logger = logging.getLogger('commands')
                commands_logger.info('%s (%d): %s %s' % (username, user_id, cmd, str(params)))

                command = commands[cmd]

                if command:
                    command.command = cmd
                    command.setParameters(user_id=user_id, username=username, chat_type=chat_type, chat_id=chat_id, parameters=params)
                    command.execute()
            except KeyError:
                pass

    async def on_close(self, boh):
        pass

async def init(app, bot, webhook_token):
    await bot.setWebhook(config.DOMAIN + config.URL + webhook_token)

async def messagesObserver(loop, bot):
    try:
        while True:
            await asyncio.sleep(1)

            if game.messages:
                message = game.messages.pop()

                if message[2] == 'message':
                    await bot.sendMessage(message[0], message[1])
                elif message[2] == 'file':
                    await bot.sendDocument(message[0], message[1])
    except:
        print('E\' successo qualcosa nel messagesObserver...') # charset issues on Hamcha's FreeBSD jail
        loop.create_task(messagesObserver(loop, bot))

def getBot(loop):
    bot = telepot.aio.DelegatorBot(config.TOKEN, [
        pave_event_space()(
            per_chat_id(), create_open, TelegramParser, timeout=10)],
        loop=loop)

    return bot

def getWebhook(bot):
    webhook = OrderedWebhook(bot)

    return webhook