import logging
import time
import datetime
import random
import os

from threading import Thread, Timer

import pymysql

import config

logger = logging.getLogger('robots')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('./logs/robots.txt', encoding='utf-8')
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

MAX_MINERS_LOG_SIZE = 16384

LOG_FMT = '_%d_%m_%Y_%H_%M_%S'
SQL_FMT = '%Y-%m-%d %H:%M:%S'
ITALIAN_FMT = '%H:%M:%S del %d-%m-%Y'

SQL_HOST = config.SQL_HOST
SQL_PORT = config.SQL_PORT
SQL_USER = config.SQL_USER
SQL_PASSWORD = config.SQL_PASSWORD
SQL_DATABASE = config.SQL_DATABASE

DELAY_TIME = 301 # 5 minuti ed un secondo
ROBOT_DELAY_TIME = 301 # 5 minuti ed un secondo

FEET_LEVEL_CAP = 101
TRACKS_LEVEL_CAP = 91

ROBOT_PRICE = 250

balls_types = ['Ball', 'NorelecBall', 'GoldBall', 'ArgentBall', 'BronzeBall', 'WoodenBall', 'BrokenBall', 'EvilBall', 'ExplosiveBall']
balls_chances = [0.7, 0.001, 0.003, 0.006, 0.03, 0.2, 0.05, 0.009, 0.001]
balls_values = dict(zip(balls_types, [1, 100, 50, 20, 10, 5, 0, -10, -20]))

robots = []
messages = []

def getHandsFormula(level):
    return level

def getHandsUpgradeFormula(level):
    return level * level

def getFeetFormula(level):
    return 3 * level

def getFeetUpgradeFormula(level):
    return level * level

def getBoxFormula(level):
    return level * 5

def getBoxUpgradeFormula(level):
    return level + 1

def getLoaderFormula(level):
    return level

def getLoaderUpgradeFormula(level):
    return level * level

def getTracksFormula(level):
    return 3 * level

def getTracksUpgradeFormula(level):
    return level * level

class CooldownException(Exception):
    def __init__(self, cooldown):
        self.seconds = int(datetime.timedelta(minutes=cooldown / 60).seconds)
        self.hours, r = divmod(self.seconds, 3600)
        self.minutes, self.seconds = divmod(r, 60)

class ExhaustedMineException(Exception):
    pass

class LevelCapException(Exception):
    pass

class BoxFullException(Exception):
    def __init__(self, ball_type):
        self.ball_type = ball_type

class NotEnoughBallsException(Exception):
    def __init__(self, diff):
        self.diff = diff

class RobotNotBoughtException(Exception):
    pass

class RobotAlreadyBoughtException(Exception):
    pass

def register(user_id, username):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'INSERT INTO players(registration_date, user_id, username, current_username) VALUES(%s, %s, %s, %s)'
    cursor.execute(sql, [datetime.datetime.today().strftime(SQL_FMT), user_id, username, username])
    db.commit()

def playerMine(user_id):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    units = getGameState(db)['units']

    if units > 0: # race condition?
        player = getPlayerByUser_id(user_id, db)

        if player['last_mine_time']:
            last_mine_time_ts = time.mktime(player['last_mine_time'].timetuple())
        else:
            last_mine_time_ts = 0

        current_time_ts = time.mktime(datetime.datetime.today().timetuple())
        time_diff = int(current_time_ts - last_mine_time_ts)

        player_delay_time = DELAY_TIME - getFeetFormula(player['feet_level'])

        if time_diff >= player_delay_time:
            ball_type = random.choices(
                balls_types, 
                balls_chances, 
                k=1
            )

            ball_type = ball_type[0]
            #ball_type = 'DoronzoBall'
            
            if player['hands_level'] == 1:
                increment = balls_values[ball_type]
            else:
                ball_value = balls_values[ball_type] - 1

                increment = getHandsFormula(player['hands_level']) + ball_value

            balls = player['balls'] + increment
            box_capacity = getBoxFormula(player['box_level'])

            if balls < 0:
                balls = 0

            if balls > box_capacity:
                ball_type = 'Ball'
                balls = player['balls'] + getHandsFormula(player['hands_level'])

            if balls <= box_capacity: # race condition?
                last_mine_time_nf = datetime.datetime.today()
                last_mine_time = last_mine_time_nf.strftime(SQL_FMT)
                
                cursor = db.cursor()
                sql = 'UPDATE players SET mined = mined + 1, balls = %s, last_mine_time = %s WHERE user_id = %s'
                cursor.execute(sql, [balls, last_mine_time, user_id])
                db.commit()
                
                units = units - getHandsFormula(player['hands_level'])

                if units < 0:
                    units = 0

                cursor = db.cursor()
                sql = 'UPDATE gamestate SET units = %s, last_miner = %s, last_mine_time = %s WHERE id = 1'
                cursor.execute(sql, [units, player['current_username'], last_mine_time])
                db.commit()

                with open('./logs/miners.txt', 'a+') as myfile:
                    myfile.write('%s alle %s ha raccolto %d palle.\n' % (player['username'], last_mine_time_nf.strftime(ITALIAN_FMT), balls - player['balls']))

                if os.path.getsize('./logs/miners.txt') > MAX_MINERS_LOG_SIZE:
                    os.rename('./logs/miners.txt', './logs/miners.txt' + datetime.datetime.today().strftime(LOG_FMT) + '.txt')
                
                return ball_type
            else:
                raise BoxFullException(ball_type)
        else:
            raise CooldownException(player_delay_time - time_diff)
    else:
        raise ExhaustedMineException()

def robotMine(user_id):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)

    player = getPlayerByUser_id(user_id, db)
    
    if player['is_robot_enabled'] == 1:
        robots_logger = logging.getLogger('robots')
        robots_logger.debug('Robot di ' + player['current_username'] + ' si è acceso!')

        units = getGameState(db)['units']

        if units > 0: # race condition?
            balls = player['balls'] + getLoaderFormula(player['loader_level'])
            box_capacity = getBoxFormula(player['box_level'])

            if balls < box_capacity: # race condition?
                robot_delay_time = ROBOT_DELAY_TIME - getTracksFormula(player['tracks_level'])

                cursor = db.cursor()
                sql = 'UPDATE players SET balls = %s WHERE user_id = %s'
                cursor.execute(sql, [balls, user_id])
                db.commit()

                units = units - player['loader_level']
                
                cursor = db.cursor()
                sql = 'UPDATE gamestate SET units = %s WHERE id = 1'
                cursor.execute(sql, [units])
                db.commit()

                if balls == 1:
                    balls_str = 'palla'
                else:
                    balls_str = 'palle'

                robots_logger.debug('Robot di ' + player['current_username'] + ' ha raccolto %d %s!' % (getLoaderFormula(player['loader_level']), balls_str))

                if player['robot_messages'] == 1:
                    sendMessage(player['user_id'], 'Il tuo robot ha raccolto %d %s!' % (getLoaderFormula(player['loader_level']), balls_str))
                
                Timer(robot_delay_time, robotMine, [user_id]).start()
            else:
                robots_logger.debug('Robot di ' + player['current_username'] + ' si è spento perchè ha il contenitore pieno.')
                sendMessage(player['user_id'], 'Il tuo robot si è spento perchè hai il contenitore pieno.')
                disableRobot(user_id, db)
        else:
            robots_logger.debug('Robot di ' + player['current_username'] + ' si è spento perchè non ci sono più palle nel castello.')
            sendMessage(player['user_id'], 'Il tuo robot si è spento perchè non ci sono più palle nel castello.')
            disableRobot(user_id, db)
    
def handsUpgrade(user_id):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    player = getPlayerByUser_id(user_id, db)
    balls = player['balls']
    hands_level = player['hands_level']
    upgrade_cost = getHandsUpgradeFormula(hands_level)
    balls = balls - upgrade_cost

    if balls >= 0:
        cursor = db.cursor()
        sql = 'UPDATE players SET balls = %s, hands_level = %s + 1 WHERE user_id = %s'
        cursor.execute(sql, [balls, hands_level, user_id])

        db.commit()
    else:
        raise NotEnoughBallsException(balls * -1)

def feetUpgrade(user_id):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    player = getPlayerByUser_id(user_id, db)
    balls = player['balls']
    feet_level = player['feet_level']
    upgrade_cost = getFeetUpgradeFormula(feet_level)
    balls = balls - upgrade_cost

    if player['feet_level'] < FEET_LEVEL_CAP:
        if balls >= 0:
            cursor = db.cursor()
            sql = 'UPDATE players SET balls = %s, feet_level = %s + 1 WHERE user_id = %s'
            cursor.execute(sql, [balls, feet_level, user_id])

            db.commit()
        else:
            raise NotEnoughBallsException(balls * -1)
    else:
        raise LevelCapException()

def boxUpgrade(user_id):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    player = getPlayerByUser_id(user_id, db)
    balls = player['balls']
    box_level = player['box_level']
    upgrade_cost = getBoxUpgradeFormula(box_level)
    balls = balls - upgrade_cost

    if balls >= 0:
        cursor = db.cursor()
        sql = 'UPDATE players SET balls = %s, box_level = %s + 1 WHERE user_id = %s'
        cursor.execute(sql, [balls, box_level, user_id])

        db.commit()
    else:
        raise NotEnoughBallsException(balls * -1)

def buyRobot(user_id):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    player = getPlayerByUser_id(user_id, db)

    if player['loader_level'] == 0 and player['tracks_level'] == 0:
        balls = player['balls'] - ROBOT_PRICE

        if balls >= 0:
            cursor = db.cursor()
            sql = 'UPDATE players SET balls = %s, is_robot_enabled = 1, loader_level = 1, tracks_level = 1 WHERE user_id = %s'
            cursor.execute(sql, [balls, user_id])

            db.commit()

            robot_delay_time = ROBOT_DELAY_TIME - getTracksFormula(player['tracks_level'])
            Timer(robot_delay_time, robotMine, [user_id]).start()
        else:
            raise NotEnoughBallsException(balls * -1)
    else:
        raise RobotAlreadyBoughtException()

def loaderUpgrade(user_id):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    player = getPlayerByUser_id(user_id, db)

    if player['loader_level'] > 0:
        balls = player['balls']
        loader_level = player['loader_level']
        upgrade_cost = getLoaderUpgradeFormula(loader_level)
        balls = balls - upgrade_cost

        if balls >= 0:
            cursor = db.cursor()
            sql = 'UPDATE players SET balls = %s, loader_level = %s + 1 WHERE user_id = %s'
            cursor.execute(sql, [balls, loader_level, user_id])

            db.commit()
        else:
            raise NotEnoughBallsException(balls * -1)
    else:
        RobotNotBoughtException()

def tracksUpgrade(user_id):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    player = getPlayerByUser_id(user_id, db)

    if player['tracks_level'] > 0:
        if player['tracks_level'] < TRACKS_LEVEL_CAP: 
            balls = player['balls']
            tracks_level = player['tracks_level']
            upgrade_cost = getTracksUpgradeFormula(tracks_level)
            balls = balls - upgrade_cost

            if balls >= 0:
                cursor = db.cursor()
                sql = 'UPDATE players SET balls = %s, tracks_level = %s + 1 WHERE user_id = %s'
                cursor.execute(sql, [balls, tracks_level, user_id])

                db.commit()
            else:
                raise NotEnoughBallsException(balls * -1)
        else:
            raise LevelCapException()
    else:
        raise RobotNotBoughtException()

def getGameState(db=None):
    if not db:
        db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    
    cursor = db.cursor(pymysql.cursors.DictCursor)
    sql = 'SELECT * FROM gamestate WHERE id = 1 FOR UPDATE'
    cursor.execute(sql)
    results = cursor.fetchall()

    if cursor.rowcount:
        return results[0]

def getPlayerByUser_id(user_id, db=None):
    if not db:
        db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    
    cursor = db.cursor(pymysql.cursors.DictCursor)
    sql = 'SELECT * FROM players WHERE user_id = %s FOR UPDATE'
    cursor.execute(sql, [user_id])
    results = cursor.fetchall()

    if cursor.rowcount:
        return results[0]

def getPlayerByCurrentUsername(current_username):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor(pymysql.cursors.DictCursor)
    sql = 'SELECT * FROM players WHERE current_username = %s'
    cursor.execute(sql, [current_username])
    results = cursor.fetchall()

    if cursor.rowcount:
        return results[0]

def updatePlayerCurrentUsername(user_id, current_username):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'UPDATE players SET current_username = %s WHERE user_id = %s'
    cursor.execute(sql, [current_username, user_id])
    db.commit()

def addAdmin(user_id):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'UPDATE players SET is_admin = 1 WHERE user_id = %s'
    cursor.execute(sql, [user_id])
    db.commit()

def delAdmin(user_id):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'UPDATE players SET is_admin = 0 WHERE user_id = %s'
    cursor.execute(sql, [user_id])
    db.commit()

def ban(user_id, ban_reason):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'UPDATE players SET is_banned = 1, ban_reason = %s WHERE user_id = %s'
    cursor.execute(sql, [ban_reason, user_id])
    db.commit()

def unban(user_id):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'UPDATE players SET is_banned = 0 WHERE user_id = %s'
    cursor.execute(sql, [user_id])
    db.commit()

def addQuote(quote):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE, charset="utf8mb4", use_unicode='True')
    cursor = db.cursor()
    sql = 'INSERT INTO quotes(text) VALUES(%s)'
    cursor.execute(sql, [quote])
    db.commit()

def delQuote(quote):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE, charset="utf8mb4", use_unicode='True')
    cursor = db.cursor()
    sql = 'DELETE FROM quotes WHERE text = %s'
    cursor.execute(sql, [quote])
    db.commit()

def getRandomQuote():
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE, charset="utf8mb4", use_unicode='True')
    cursor = db.cursor(pymysql.cursors.DictCursor)
    sql = 'SELECT * FROM quotes ORDER BY RAND() LIMIT 1'
    cursor.execute(sql)
    results = cursor.fetchall()

    if cursor.rowcount:
        return results[0]['text']

def getQuotes():
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE, charset="utf8mb4", use_unicode='True')
    cursor = db.cursor(pymysql.cursors.DictCursor)
    sql = 'SELECT * FROM quotes'
    cursor.execute(sql)
    results = cursor.fetchall()

    if cursor.rowcount:
        return results

def addBalls(user_id=None, db=None):
    if user_id:
        pass
    else:
        pass

def addHandsLevel(user_id, hands_level):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'UPDATE players SET hands_level = hands_level + %s WHERE user_id = %s'
    cursor.execute(sql, [hands_level, user_id])
    db.commit()

def delHandsLevel(user_id, hands_level):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'UPDATE players SET hands_level = hands_level - %s WHERE user_id = %s'
    cursor.execute(sql, [hands_level, user_id])
    db.commit()

def addFeetLevel(user_id, feet_level):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'UPDATE players SET feet_level = feet_level + %s WHERE user_id = %s'
    cursor.execute(sql, [feet_level, user_id])
    db.commit()

def delFeetLevel(user_id, feet_level):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'UPDATE players SET feet_level = feet_level - %s WHERE user_id = %s'
    cursor.execute(sql, [feet_level, user_id])
    db.commit()

def addBoxLevel(user_id, box_level):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'UPDATE players SET box_level = box_level + %s WHERE user_id = %s'
    cursor.execute(sql, [box_level, user_id])
    db.commit()

def delBoxLevel(user_id, box_level):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'UPDATE players SET box_level = box_level - %s WHERE user_id = %s'
    cursor.execute(sql, [box_level, user_id])
    db.commit()

def addLoaderLevel(user_id, loader_level):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'UPDATE players SET loader_level = loader_level + %s WHERE user_id = %s'
    cursor.execute(sql, [loader_level, user_id])
    db.commit()

def delLoaderLevel(user_id, loader_level):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'UPDATE players SET loader_level = loader_level - %s WHERE user_id = %s'
    cursor.execute(sql, [loader_level, user_id])
    db.commit()

def addTracksLevel(user_id, tracks_level):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'UPDATE players SET tracks_level = tracks_level + %s WHERE user_id = %s'
    cursor.execute(sql, [tracks_level, user_id])
    db.commit()

def delTracksLevel(user_id, tracks_level):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'UPDATE players SET tracks_level = tracks_level - %s WHERE user_id = %s'
    cursor.execute(sql, [tracks_level, user_id])
    db.commit()

def addGoldHamcha(user_id, gold_hamcha):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'UPDATE players SET gold_hamcha = gold_hamcha + %s WHERE user_id = %s'
    cursor.execute(sql, [gold_hamcha, user_id])
    db.commit()

def delGoldHamcha(user_id, gold_hamcha):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'UPDATE players SET gold_hamcha = gold_hamcha - %s WHERE user_id = %s'
    cursor.execute(sql, [gold_hamcha, user_id])
    db.commit()

def getTitleByText(text):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE, charset="utf8mb4", use_unicode='True')
    cursor = db.cursor(pymysql.cursors.DictCursor)
    sql = 'SELECT * FROM titles WHERE text = %s'
    cursor.execute(sql, [text])
    results = cursor.fetchall()

    if cursor.rowcount:
        return results[0]

def getPlayerTitles(user_id):
    player = getPlayerByUser_id(user_id)

    if player:
        db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE, charset="utf8mb4", use_unicode='True')
        cursor = db.cursor(pymysql.cursors.DictCursor)
        sql = 'SELECT * FROM players, players_titles, titles WHERE players.id = %s AND players.id = players_titles.id_player AND players_titles.id_title = titles.id'
        cursor.execute(sql, [player['id']])
        results = cursor.fetchall()

        if cursor.rowcount:
            return results

def addTitle(user_id, text):
    title = getTitleByText(text)

    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE, charset="utf8mb4", use_unicode='True')

    if not title:
        cursor = db.cursor()
        sql = 'INSERT INTO titles(text, date) VALUES (%s, %s)'
        cursor.execute(sql, [text, datetime.datetime.today().strftime(SQL_FMT)])
        db.commit()

        id_title = cursor.lastrowid
    else:
        id_title = title['id']

    player_titles = getPlayerTitles(user_id)

    found = False

    if player_titles:
        for player_title in player_titles:
            if id_title == player_title['id_title']:
                found = True
                break
    
    if not found:
        player = getPlayerByUser_id(user_id)

        cursor = db.cursor()
        sql = 'INSERT INTO players_titles(id_player, id_title) VALUES (%s, %s)'
        cursor.execute(sql, [player['id'], id_title])
        db.commit()

def delTitle(user_id, text):
    title = getTitleByText(text)

    if title:
        player = getPlayerByUser_id(user_id)

        db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE, charset="utf8mb4", use_unicode='True')
        cursor = db.cursor()
        sql = 'DELETE FROM players_titles WHERE id_player = %s AND id_title = %s'
        cursor.execute(sql, [player['id'], title['id']])
        db.commit()

        cursor = db.cursor(pymysql.cursors.DictCursor)
        sql = 'SELECT * FROM players_titles WHERE id_title = %s'
        cursor.execute(sql, [title['id']])
        results = cursor.fetchall()

        if not cursor.rowcount:
            cursor = db.cursor()
            sql = 'DELETE FROM titles WHERE id = %s'
            cursor.execute(sql, [title['id']])
            db.commit()

def disableAllRobots():
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'UPDATE players SET is_robot_enabled = 0 WHERE is_robot_enabled = 1'
    cursor.execute(sql)
    db.commit()

def enableRobot(user_id):
    player = getPlayerByUser_id(user_id)

    if player['loader_level'] > 0 and player['tracks_level'] > 0:
        if not player['is_robot_enabled']:
            db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
            cursor = db.cursor()
            sql = 'UPDATE players SET is_robot_enabled = 1 WHERE user_id = %s'
            cursor.execute(sql, [user_id])
            db.commit()

            robot_delay_time = ROBOT_DELAY_TIME - getTracksFormula(player['tracks_level'])
            timer = Timer(robot_delay_time, robotMine, [user_id])
            timer.start()
            robots.append([user_id, timer])
    else:
        raise RobotNotBoughtException()

def disableRobot(user_id, db=None):
    if not db:
        db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)

    player = getPlayerByUser_id(user_id, db)

    if player['loader_level'] > 0 and player['tracks_level'] > 0:
        cursor = db.cursor()
        sql = 'UPDATE players SET is_robot_enabled = 0 WHERE user_id = %s'
        cursor.execute(sql, [user_id])
        db.commit()

        for robot in robots:
            if user_id == robot[0]:
                robot[1].cancel()

        robots_logger = logging.getLogger('robots')
        robots_logger.debug('Robot di ' + player['current_username'] + ' si è spento.')
        sendMessage(user_id, 'Il tuo robot si è spento.')
    else:
        raise RobotNotBoughtException()

def enableRobotMessages(user_id):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'UPDATE players SET robot_messages = 1 WHERE user_id = %s'
    cursor.execute(sql, [user_id])
    db.commit()

def disableRobotMessages(user_id):
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor()
    sql = 'UPDATE players SET robot_messages = 0 WHERE user_id = %s'
    cursor.execute(sql, [user_id])
    db.commit()

def generateInfoHTML():
    gamestate = getGameState()

    info = '<html><head><title>Palle di Norelec</title><body><h1>Palle di Norelec</h1>'
    info = info + '<p>Ultima palla raccolta da %s alle %s. Mancano %d palle da raccogliere.</p><p>' % (gamestate['last_miner'], gamestate['last_mine_time'].strftime(ITALIAN_FMT), gamestate['units'])

    for line in reversed(list(open("./logs/miners.txt"))):
        info = info + '<br />' + line.rstrip()
    
    info = info + '</p></body></html>'

    return info

def sendMessage(chat_id, msg):
    messages.append([chat_id, msg, 'message'])

def sendFile(chat_id, document):
    messages.append([chat_id, document, 'file'])

def getPlayers():
    db = pymysql.connect(host=SQL_HOST, port=SQL_PORT, user=SQL_USER, passwd=SQL_PASSWORD, db=SQL_DATABASE)
    cursor = db.cursor(pymysql.cursors.DictCursor)
    sql = 'SELECT * FROM players'
    cursor.execute(sql)
    results = cursor.fetchall()

    return results

def sendMessageAll(msg):
    players = getPlayers()

    for player in players:
        sendMessage(player['chat_id'], msg)