

import discord # definitely not native
from discord.ext import commands

import datetime, re
# import random
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

description = '''An open source Kancolle helper bot for Discord.'''
command_prefix = '+' # change to whatever you see fit
bot = commands.Bot(command_prefix, description=description)

# initalizes token from config.yaml and commandMatrix from orders.yaml.
config = yaml.load(open('config.yaml','r'))
global token
token = config['token']
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

    print('commandMatrix, questMatrix, servers, channels, admins updated.')

def updateOnCommand(message):
    update()
    asyncio.ensure_future(on_command_DM(message,'commandMatrix, questMatrix, servers, channels, admins updated.'))

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
    print('scheduledposts() got called.')
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

    update()


    print('------')
    print('Logged in as:')
    print('Username: ' + bot.user.name)
    print('      ID: ' + bot.user.id)
    print('------')
    # Scheduled messages using schedule
    asyncio.ensure_future(scheduledposts())
    # Startup message
    await sendToAllAdmins('Akizuki, setting sail!')

    initialize_schedule()


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

def printCommand(message,command,fixed,terms=''):
    command = command_prefix + command
    if fixed:
        command = command_prefix + command
    if terms: # account for if list and not single string
        command = command + ' ' + terms
    if message.channel.is_private:
        print('\"' + command + '\"' + ' was called in ' + message.author.name + ' (ID#' + message.author.id + ')\'s DMs.')
        return
    print('\"' + command + '\"' + ' was called in ' + message.channel.name + ' (ID#' + message.channel.id + ') in ' + message.server.name + ' (ID#' + message.server.id  + ')')



# This works. Bot commands don't. I'll just stick with client fake commands.
@bot.event
async def on_message(message):

    # akizuki shouldn't talk to herself, listen to things that aren't commands, or servers that aren't whitelisted
    # if (message.author == bot.user or (not message.content.startswith(command_prefix)) or ((message.server not in servers) and (not message.channel.is_private) and (message.author not in admins))) :
    if (message.author == bot.user or (not message.content.startswith(command_prefix))) :
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
            printCommand(message,command,fixed)
            await on_command(message,message.channel,todo,fixed) # TODO: need to account for commands not intended to last for 60s
        elif callable(todo):
            printCommand(message,command,fixed)
            todo(message,message.channel,terms,fixed)
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

    if command in ['wikia', 'wiki']:
        searchTerm = ' '.join(terms)
        searchURL = urllib.parse.quote_plus(searchTerm)
        if not searchTerm:
            await on_command(message,message.channel, 'http://kancolle.wikia.com/wiki/Kancolle_Wiki',fixed)
        else:
                searched = requests.get('http://kancolle.wikia.com/api/v1/Search/List?query='+searchURL).json()
                if 'items' in searched:
                    await on_command(message,message.channel, searched['items'][0]['url'],fixed)
                else:
                    await on_command(message,message.channel, 'No result found.',False,10)
  
    if command in ['quest']:
        if terms[0] in questMatrix.keys():
            await on_command(message,message.channel, questMatrix[terms[0]],fixed)
        else:
            await on_command(message,message.channel, 'No such quest found.',False,10)

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
                    printCommand(message,command,fixed)
                except discord.errors.InvalidArgument:
                    bot.send_message(message.channel, 'That didn\'t work. Did you remember to include a channel ID?')
                    return
            else:
                try:
                    await bot.delete_message(message)
                except discord.errors.Forbidden:
                    # so you look less like a right bellend
                    return
                to_say = ' '.join(shlex.split(message.content[prefix_len:])[1:])
                await bot.send_message(message.channel, to_say)
                printCommand(message,command,fixed)

    # Owner command(s)
    # proper shutdown command
    if command in ['shutdown', 'sd']:
        if message.author.id in admins:
            try:
                await bot.delete_message(message)
            except discord.errors.Forbidden:
                pass 
            await sendToAllAdmins('Returning to base.')
            await asyncio.sleep(10)

bot.run(token)
