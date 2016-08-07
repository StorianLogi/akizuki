

import discord # definitely not native
from discord.ext import commands

import datetime, re
import schedule # not native
import json # not native iirc
import time
import yaml # not native iirc
import asyncio  # not native iirc
import sys
import shlex # built-in to 3.5
import requests
import urllib.parse # built-in to 3.5
from typing import List
import logging

description = '''An open source Kancolle helper bot for Discord.'''
command_prefix = '+' # change to whatever you see fit
bot = commands.Bot(command_prefix, description=description)
# logging.basicConfig(filename='captains.log',format='[%(asctime)s]: %(message)s', datefmt='%Y/%m/%d %H:%M:%S',level=logging.INFO)
captainsLog = logging.getLogger('logbook')
captainsLog.setLevel(logging.INFO)
pen = logging.FileHandler('captains.log')
pen.setLevel(logging.INFO)
sty = logging.Formatter('[%(asctime)s]: %(message)s', '%Y/%m/%d %H:%M:%S')
pen.setFormatter(sty)
captainsLog.addHandler(pen)
voz = logging.StreamHandler(sys.stdout,)
voz.setLevel(logging.INFO)
voz.setFormatter(sty)
captainsLog.addHandler(voz)

# initalizes token from config.yaml and commandMatrix from orders.yaml.
config = yaml.load(open('config.yaml','r'))
global token
token = config['token']
global admins

global commandMatrix
commandMatrix = yaml.load(open('rigging/orders.yaml','r'))

global alreadyRunning
alreadyRunning = False

# make sure all orders and config data are up-to-date
def update():
    global commandMatrix
    global questMatrix
    # assemble all commands akizuki will respond to on message into this matrix 
    # will receive message, fixed, and terms
    # parse so if isinstance(commandMatrix['command'], str) do on_command(message,message.channel,str,fixed)
    # else run the function with the given message, fixed, terms
    commandMatrix.update(yaml.load(open('rigging/orders.yaml','r')))
    questData = requests.get('https://raw.githubusercontent.com/KC3Kai/kc3-translations/master/data/en/quests.json').json()

    questMatrix = {}
    for key in questData.keys():
        questMatrix.update(dict.fromkeys([questData[key]['code'].lower()],'Quest '+questData[key]['code']+': '+questData[key]['desc']))
    commandMatrix.update(questMatrix)


    global servers
    global channels
    global admins

    #TODO: get the servercheck working xP
    #TODO: test with multiple servers
    if isinstance(config['servers'],list):
        servers = [bot.get_server(str(s)) for s in config['servers']]
    else:
        servers = [bot.get_server(str(['servers'])),]

    # TODO: test with single channel
    if isinstance(config['channels'],list):
        channels = [discord.Object(c) for c in config['channels']]
    else:
        channels = [discord.Object(config['channels']),]

    # TODO: test with multiple admins
    if isinstance(config['admins'],list):
        admins = [str(a) for a in config['admins']]
    else:
        admins = [str(config['admins']),]

    captainsLog.info('commandMatrix, questMatrix, servers, channels, admins updated.')

def updateOnCommand(message):
    update()
    asyncio.ensure_future(on_command_DM(message,'commandMatrix, questMatrix, servers, channels, admins updated.'))

# # So we don't have to drop an "await" in front of all these upcoming commands
# def makeCommandsCallable(command):
#     return lambda: asyncio.ensure_future(command)

# Commands too complicated to (easily) load in via yaml.
# The callable on on_message provides (message,message.channel,terms,fixed) which must included in arguments for commands added to the commandMatrix even if they aren't used or else we get a runtime error.
# There's probably a way to bypass this in python but I don't know it.
async def searchKCWikia(message,channel,terms,fixed):
    searchTerm = ' '.join(terms)
    searchURL = urllib.parse.quote_plus(searchTerm)
    if not searchTerm:
        await on_command(message,channel, 'http://kancolle.wikia.com/wiki/Kancolle_Wiki',fixed)
    else:
            searched = requests.get('http://kancolle.wikia.com/api/v1/Search/List?query='+searchURL).json()
            if 'items' in searched:
                await on_command(message,channel, searched['items'][0]['url'],fixed)
            else:
                await on_command(message,channel, 'No result found.',False,10)
commandMatrix.update(dict.fromkeys(['search'],searchKCWikia))

async def callKCWikia(message,channel,terms,fixed):
    if terms :
        await searchKCWikia(message,channel,terms,fixed)
    else :
        await on_command(message,channel, 'http://kancolle.wikia.com/wiki/Kancolle_Wiki',fixed)
commandMatrix.update(dict.fromkeys(['wiki'],callKCWikia))
commandMatrix.update(dict.fromkeys(['wikia'],callKCWikia))

async def questQuery(message,channel,terms,fixed): # +quest [questcode] OR +[questcode]
    if terms[0] in questMatrix.keys():
        await on_command(message,channel, questMatrix[terms[0]],fixed)
    else:
        await on_command(message,channel, 'No such quest found.',False,10)
commandMatrix.update(dict.fromkeys(['quest'],questQuery))





# commands only usable by users with admin-listed ids
adminMatrix = {}
adminMatrix.update(dict.fromkeys(['ping'], 'ポン!'))
adminMatrix.update(dict.fromkeys(['update'], updateOnCommand))


async def send_to_all_channels(message: str) : # -> List[Message]:
    global channels
    messages = []
    for channel in channels:
        try:
            messages.append(await bot.send_message(channel, message))
        except (discord.errors.Forbidden, discord.errors.NotFound) as n:
            pass

    return messages

async def sendToAllAdmins(message: str) :
    global admins
    global servers
    for admin in admins:
        for server in servers:
            try:
                await bot.send_message(server.get_member(admin), message)
            except (discord.errors.Forbidden, discord.errors.NotFound) as n:
                pass

def construct_reminder_func(message):
    return lambda: asyncio.ensure_future(send_to_all_channels(message))

    
pvp_reset_early = construct_reminder_func('PVP reset in 1 hour.\n(Ranking point cutoff for this cycle now.)')
pvp_reset = construct_reminder_func('PVP reset')
quest_reset_early = construct_reminder_func('Quest reset in 1 hour.')
quest_reset = construct_reminder_func('Quest reset.')
weekly_reset_early = construct_reminder_func('It\\\'s a weekly reset, too!')
weekly_reset = construct_reminder_func('Weekly reset.')



# ship data module
# como did this part. i only have the faintest idea of what's going on here.
json_data = requests.get('https://raw.githubusercontent.com/gakada/KCTools/master/Lib/Data/ShipData.json').json()

def fix_key(key):
    if len(key) > 0 and key[0] == '_':
        return key[1:]
    return key

def create_ship_yaml_mapping():
    result = {}
    for ship_name, ship_data in json_data.items():
        for ship_suffix, stats_data in ship_data.items():
            if isinstance(stats_data,dict):
                if len(ship_suffix) > 0:
                    full_name = '{} {}'.format(ship_name, ship_suffix).lower()
                else:
                    full_name = ship_name.lower()
                
                result[full_name] = dict((fix_key(key), val) for key, val in stats_data.items())
    return result

ship_data = create_ship_yaml_mapping()



# Timed messages using schedule. This stuff works but can only do as far as weeklies.
# Will need to switch to APscheduler for more comprehensive reminders.
async def scheduledposts():
    captainsLog.info('Posts have been scheduled.')
    while not bot.is_closed:
        schedule.run_pending()
        await asyncio.sleep(15) # Change to 30 or 60 if too intensive to run.

def initialize_schedule():
    # currently running off a laptop in PDT
    schedule.every().day.at("10:00").do(pvp_reset_early) # 2 JST
    schedule.every().day.at("22:00").do(pvp_reset_early) # 14 JST
    schedule.every().day.at("11:00").do(pvp_reset) # 3 JST
    schedule.every().day.at("23:00").do(pvp_reset) # 15 JST
    schedule.every().day.at("12:00").do(quest_reset_early) # 4 JST
    schedule.every().day.at("13:00").do(quest_reset) # 5 JST
    schedule.every().sunday.at("12:00").do(weekly_reset_early) # Monday 4 JST
    schedule.every().sunday.at("13:00").do(weekly_reset) # Monday 4 JST

# # Timed messages using APscheduler
# scheduler = AsyncIOScheduler()
# scheduler.add_job(notify_func, 'cron', hour='10', timezone=datetime.tzinfo.tzname('JST'))
# scheduler.start()



# Startup script.
@bot.event
async def on_ready():
    global alreadyRunning
    if alreadyRunning:
        return
    else:
        alreadyRunning = True

    print('------')
    update()    
    captainsLog.info('Akizuki launched.')
    print('Logged in as:')
    print('Username: ' + bot.user.name)
    print('      ID: ' + bot.user.id)
    # Scheduled messages using schedule
    asyncio.ensure_future(scheduledposts())
    initialize_schedule()
    print('------')

    # Startup message
    await sendToAllAdmins('Akizuki, setting sail!')



# for use in channels
async def on_command(message,channel,text,fixed=False,time=60):
    try:
        d = await bot.send_message(channel,text)
    except discord.errors.Forbidden:
        pass    
    if not fixed:
        await asyncio.sleep(time)
        await bot.delete_message(d)
        try:
            await bot.delete_message(message)
        except discord.errors.Forbidden:
            return

# for use in in-channel commands returning a DM (eg +help)
async def on_command_DM(message,text):
    await bot.send_message(message.author,text)
    try:
        await bot.delete_message(message)
    except discord.errors.Forbidden:
        return

def commandReport(message,command,fixed,terms=''):
    command = command_prefix + command
    if fixed:
        command = command_prefix + command
    if terms:
        terms = ' '.join(terms)
        command = command + ' ' + terms
    if message.channel.is_private:
        report = command + ' by ' + message.author.name + ' <@' + message.author.id + '> DM'
    else:
        report = command + ' by ' + message.author.name + ' <@' + message.author.id + '> in #' + message.channel.name + ' <#' + message.channel.id + '> of ' + message.server.name + ' (ID#' + message.server.id  + ')'
    return report



# discord.py Bot class commands don't work, so Bot is used as an extension of Client.
@bot.event
async def on_message(message):

    global servers
    # akizuki shouldn't talk to herself
    if message.author == bot.user :
        return
    # akizuki logs DMs to file and checks if an admin sent it. akizuki will not respond to DMs not by admins.
    # If an admin sent it, she'll check if it was a command. If it is, it'll go through the process.
    elif message.channel.is_private :
        if message.attachments :
            captainsLog.info(message.author.name + ' <@' + message.author.id + '> DM: ' + message.content + ' [' + message.attachments[0]['filename'] + ']\n' + message.attachments[0]['url'])
        else :
            captainsLog.info(message.author.name + ' <@' + message.author.id + '> DM: ' + message.content)
        global admins
        if (message.author.id not in admins or (not message.content.startswith(command_prefix))) :
            return
    # akizuki shouldn't listen to things that aren't commands or servers that aren't whitelisted
    elif (message.server not in servers or (not message.content.startswith(command_prefix))) :
        return


    if message.content.startswith(command_prefix + command_prefix):
        fixed = True
        prefix_len = len(command_prefix) * 2
    else:
        fixed = False
        prefix_len = len(command_prefix)

    parsed_message = shlex.split(message.content.lower()[prefix_len:])
    command = parsed_message[0]
    terms = parsed_message[1:]
    print(command)

    # any function that responds to a message will take the triggering message "message", whether or not to not delete the triggering message and its reponse "fixed", and any additional terms that refine the general command "terms"

    if command in list(commandMatrix.keys()):
        todo = commandMatrix[command]
        if isinstance(todo, str):
            captainsLog.info(commandReport(message,command,fixed))
            await on_command(message,message.channel,todo,fixed) # TODO: need to account for commands not intended to last for 60s
        elif callable(todo):
            captainsLog.info(commandReport(message,command,fixed))
            asyncio.ensure_future(todo(message,message.channel,terms,fixed)) # note the await. none of these commands will not involve posting something to discord (and therefore requiring an await)
        else:
            print('something went wrong with ' + message.content[:(prefix_len-1)] + command)
        return
    elif (command in list(adminMatrix.keys())) and (message.author.id in admins):
        todo = adminMatrix[command]
        if isinstance(todo, str):
            await on_command_DM(message,todo)
        elif callable(todo):
            todo(message) # better not write anything that actually does stuff with commands
        else:
            print('something went wrong with admin command ' + message.content[:(prefix_len-1)] + command)
        return

    # There must be a better way.
    if command == 'help':
        await on_command_DM(message,'Non-exhaustive list of commands:\n```' + command_prefix + 'info, ' + command_prefix + 'library, ' + command_prefix + 'improvements, ' + command_prefix + 'fit, ' + command_prefix + 'wikia, ' + command_prefix + 'wikiwiki, ' + command_prefix + 'poi-stats, ' + command_prefix + 'poi-viewer' + ', and so on.```\nUse '+command_prefix+command_prefix+' if you\'d like to sticky your command and my response.')

    # dfw changing avatars manually doesn't work
    # if command == 'change':
    #     await bot.edit_profile(avatar=open('akizuki.jpg','rb').read())
    #     await on_command(message,message.channel, 'done',fixed)

    if command == 'ship':
        rest = ' '.join(parsed_message[1:])
        if rest in ship_data:
            formatted_result = '```' + yaml.dump(ship_data[rest], default_flow_style=False) + '```'
            await on_command(message, message.channel, formatted_result, 30)

    # use ///" and ///' if you want to use those characters
    if command in ['say']:
        if message.author.id in admins:
            if message.channel.is_private:
                whereToSay = bot.get_channel(terms[0])
                to_say = ' '.join(shlex.split(message.content[prefix_len:])[2:])
                try:
                    await bot.send_message(whereToSay, to_say)
                except discord.errors.InvalidArgument:
                    bot.send_message(message.channel, 'That didn\'t work. Did you remember to include a channel ID?')
                    return
                captainsLog.info(commandReport(message,command,fixed,terms))
            else:
                try:
                    await bot.delete_message(message)
                except discord.errors.Forbidden:
                    # so you look less like a right bellend
                    return
                to_say = ' '.join(shlex.split(message.content[prefix_len:])[1:])
                await bot.send_message(message.channel, to_say)
                captainsLog.info(commandReport(message,command,fixed,terms))

    # Owner command(s)
    # proper shutdown command
    if command in ['shutdown', 'sd']:
        if message.author.id in admins:
            try:
                await bot.delete_message(message)
            except discord.errors.Forbidden:
                pass 
            await sendToAllAdmins('Returning to base.')
            captainsLog.info('Akizuki returned.')
            sys.exit()

bot.run(token)
