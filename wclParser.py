import requests
import datetime
import time
import math
from test.test_threading_local import target

all_bosses = [2032, 2048, 2036, 2037, 2050, 2054, 2052, 2038, 2051]
fightCache = {}
difficulties = {'lfr':1,
				'normal':3,
				'heroic':4,
				'mythic':5}
api_key = "6f5214bba2c2ed4cad6800c6a57c3118"
classes = {'death knight':1, 'druid':2, 'hunter':3, 'mage':4, 'monk':5, 'paladin':6, 'priest':7,
		   'rogue':8, 'shaman':9, 'warlock':10, 'warrior':11,'demon hunter':12}
hasteScale = 375
mastScale = 320
versScale = 475
critScale = 400
#todo: clean up events init functions (super, whoops)

class eventWatch():

	name = "Event Count"

	def __init__(self, abilityID = None, eventType = None, source = "player", target = None,
				 sentinel = False):
		self.abilityID = [abilityID]
		self.eventType = eventType
		self.source = source
		self.target = target

	def __str__(self):
		return self.type + ':' + str(self.abilityID)[1:-1]

	def getEvents(self):
		return self.eventType

	def memInit(self):
		return 0

	def getMemory(self):
		return str(type(self).__name__) + str(self.abilityID)[1:-1] + str(self.source) + str(self.target)

	def operation(self, event, memory):
		memory[self.getMemory()] += 1

	def postOp(self, events, memory):
		return memory[self.getMemory()]

class uptimeWatch(eventWatch):

	name = "Uptime"
	
	def getEvents(self):
		return ['applybuff', 'removebuff', 'applydebuff', 'removedebuff']

	def memInit(self):
		return {'total':0}

	def operation(self,event,memory):
		if event['type'] == 'applybuff' or event['type'] == 'applydebuff':
			memory[self.getMemory()][event['targetID']] = event['timestamp']
		else:
			if event['targetID'] in memory[self.getMemory()].keys():
				memory[self.getMemory()]['total'] += event['timestamp'] - memory[self.getMemory()][event['targetID']]

	def postOp(self, events, memory):
		return memory[self.getMemory()]['total'] / (events[len(events)-1]['timestamp'] - events[0]['timestamp'])

class statWatch(eventWatch):

	name = "Stat Info"
	
	def __init__(self, abilityID = None, statName = None, eventType = None, source = 'player', target = None, sentinel = False, targetVal = None, op = None):
		self.statName = statName
		return super().__init__(abilityID, eventType, source, target, sentinel, targetVal, op)

	def getEvents(self):
		return 'combatantinfo'

	def getMemory(self):
		return str(type(self).__name__) + str(self.abilityID)[1:-1] + str(self.source) + str(self.target) + str(self.statName)
	
	def operation(self, event, memory):
		if self.statName in event.keys():
			memory[self.getMemory()] = event[self.statName]

class healingWatch(eventWatch):

	def getEvents(self):
		return 'heal'

	def operation(self, event, memory):
		memory[self.getMemory()] += event['amount']
		if 'absorbed' in event.keys():
			memory[self.getMemory()] += event['absorbed']

class healRawWatch(eventWatch):

	def getEvents(self):
		return 'heal'

	def operation(self, event, memory):
		memory[self.getMemory()] += event['amount'] + (event['overheal'] if 'overheal' in event.keys() else 0)
		+(event['absorbed'] if 'absorbed' in event.keys() else 0)

class statBuff():
	def __init__(self, type, abilityID, magnitudePercent = None, magnitudeRating = None, name = None, stacked = False):
		if type == "haste":
			self.scale = hasteScale
		elif type == "mastery":
			self.scale = mastScale
		elif type == "crit":
			self.scale = critScale
		elif type == "vers":
			self.scale = versScale
		self.abilityID = abilityID
		if magnitudePercent == None:
			self.magnitude = magnitudeRating/(self.scale * 100)
		else:
			self.magnitude = magnitudePercent
		self.name = name
		self.stacked = stacked

class trinketStatBuff():
	def __init__(self, baseRating, type, abilityID, itemID, baseIlvl = 900, scaling = 2, name = None, stacked = False, noScalePercent = None):
		self.baseRating = baseRating
		self.baseIlvl = baseIlvl
		self.abilityID = abilityID
		self.itemID = itemID
		self.scaling = scaling
		self.name = name
		self.stacked = stacked
		self.noScalePercent = noScalePercent
		if type == "haste":
			self.scale = hasteScale
		elif type == "mastery":
			self.scale = mastScale
		elif type == "crit":
			self.scale = critScale
		elif type == "vers":
			self.scale = versScale

	def calcMagnitude(self, ilvl):
		if self.noScalePercent:
			return self.noScalePercent
		if self.scaling == 2:
			return (self.baseRating * 1.15 ** ((ilvl - self.baseIlvl)/15) * 0.994435486 ** (ilvl - self.baseIlvl))/(self.scale*100)
		elif self.scaling == 1:
			return (self.baseRating * 1.15 ** ((ilvl - self.baseIlvl)/15))/(self.scale*100)

		#todo: chrono shard set bonuses and proper antitoxin scaling
hasteBuffs = [statBuff(abilityID = 2825, magnitudePercent = 0.3, name = "Bloodlust", type = "haste"),
			  statBuff(abilityID = 240673, magnitudeRating = 800, name = "Mind Quickening", type = "haste"),
			  statBuff(abilityID = 202842, magnitudePercent = 0.1, name = "Rapid Innervation", type = "haste"),
			  statBuff(abilityID = 80353, magnitudePercent = 0.3, name = "Time Warp", type = "haste"),
			  trinketStatBuff(abilityID=242543, itemID = 147005, name = "Lunar Infusion", baseRating = 3619, type = "haste"),
			  trinketStatBuff(abilityID=242458, itemID = 147002, name = "Rising Tides", baseRating = 576, stacked = True, type = "haste"),
			  trinketStatBuff(abilityID=214120, itemID = 137419, name = "Acceleration", baseRating = 6473, type = "haste"),
			  statBuff(abilityID=26297, magnitudePercent=0.15, name = "Berserking", type = "haste"),
			  statBuff(abilityID=208051, magnitudePercent=0.23, name = "Sephuz's Secret", type = "haste"),
			  statBuff(abilityID=224147, magnitudeRating=3000, name="Nightwell Arcanum", type="haste"),
			  statBuff(abilityID=202842, magnitudePercent=0.1, name="Rapid Innervation", type="haste"),
			  trinketStatBuff(abilityID=225753, itemID=140803, baseRating=4275, name="Sign of the Dragon", type="haste"),
			  trinketStatBuff(abilityID=238501, itemID=144480, baseRating=4275, name="Swarming Shadows", type="haste"),
			  trinketStatBuff(abilityID=224347, itemID=137484, baseRating=421, name="Solemnity", type="haste", stacked = True),
			  statBuff(abilityID=214140, magnitudeRating=905, name = "Nether Anti-toxin", type="haste"),
			  trinketStatBuff(abilityID=221748, itemID=129330, baseRating=1432, name="Heightened Senses", type="haste"),
			  statBuff(abilityID=190909, magnitudeRating=1000, name="Mark of the Claw", type="haste"),
			  statBuff(abilityID=225603, magnitudeRating=375, name="Well Fed", type="haste")]

class hasteWatch(eventWatch):
	def __init__(self):
		self.abilityID = []
		for buff in hasteBuffs:
			self.abilityID.append(buff.abilityID)
		self.source = None
		self.target = "player"

	def getEvents(self):
		return ['combatantinfo','applybuff', 'applydebuff', 'removebuff', 'removedebuff',  'applybuff', 'applybuffstack', 'removebuffstack']

	def getMemory(self):
		return 'hasteWatch'
	
	def memInit(self):
		mem = {'haste':0,
		  'trinkets':{},
		  'stacks':{}}
		for i in [x for x in hasteBuffs if x.stacked]:
			mem['stacks'][i.abilityID] = 0
		return mem

	def operation(self, event, memory):
		if event['type'] == 'combatantinfo':
			memory[self.getMemory()]['haste'] = 1 + event['hasteSpell']/(hasteScale*100)
			for gear in event['gear']:
				if gear['id'] == 132452:
					memory[self.getMemory()]['haste'] += 0.02
				for trinket in [buff for buff in hasteBuffs if type(buff) is trinketStatBuff]:
					if gear['id'] == trinket.itemID:
						memory[self.getMemory()]['trinkets'][buff.abilityID] = buff.calcMagnitude(gear['itemLevel'])
		if event['type'] == 'applybuff' or event['type'] == 'applydebuff':
			for buff in hasteBuffs:
				if buff.abilityID == event['ability']['guid']:
					if buff.stacked:
						memory[self.getMemory()]['stacks'][buff.abilityID] += 1
					if type(buff) is trinketStatBuff:
						memory[self.getMemory()]['haste'] += memory[self.getMemory()]['trinkets'][buff.abilityID]
					else:
						memory[self.getMemory()]['haste'] += buff.magnitude
		if event['type'] == 'removebuff' or event['type'] == 'removedebuff':
			for buff in hasteBuffs:
				if buff.abilityID == event['ability']['guid']:
					if buff.stacked:
						memory[self.getMemory()]['stacks'][buff.abilityID] = 0
						if type(buff) is trinketStatBuff:
							memory[self.getMemory()]['haste'] -= memory[self.getMemory()]['stacks'] * memory[self.getMemory()]['trinkets'][buff.abilityID]
						else:
							memory[self.getMemory()]['haste'] -= memory[self.getMemory()]['stacks'] * buff.magnitude
					else:
						if type(buff) is trinketStatBuff:
							memory[self.getMemory()]['haste'] -= memory[self.getMemory()]['trinkets'][buff.abilityID]
						else:
							memory[self.getMemory()]['haste'] -= buff.magnitude
		if event['type'] == 'applybuffstack' or event['type'] == 'applydebuffstack' or event['type'] == 'removebuffstack' or event['type'] == 'removedebuffstack':
			for buff in hasteBuffs:
				if buff.abilityID == event['ability']['guid']:
					if type(buff) is trinketStatBuff:
						memory[self.getMemory()]['haste'] -= memory[self.getMemory()]['stacks'][buff.abilityID] * memory[self.getMemory()]['trinkets'][buff.abilityID]
						memory[self.getMemory()]['haste'] += event['stacks'] * memory[self.getMemory()]['trinkets'][buff.abilityID]
					else:
						memory[self.getMemory()]['haste'] -= memory[self.getMemory()]['stacks'][buff.abilityID] * buff.magnitude
						memory[self.getMemory()]['haste'] += event['stacks'] * buff.magnitude
					memory[self.getMemory()]['stacks'][buff.abilityID] = event['stacks']
			





class overhealWatch(eventWatch):

	def getEvents(self):
		return 'heal'

	def memInit(self):
		return {'healing':0, 'overheal':0}

	def operation(self, event, memory):
		memory[self.getMemory()]['healing'] += event['amount']
		if 'absorbed' in event.keys():
			memory[self.getMemory()]['healing'] += event['absorbed']
		if 'overheal' in event.keys():
			memory[self.getMemory()]['overheal'] += event['overheal']

	def postOp(self, events, memory):
		#in case crotchbomb forgets to use a trinket or something
		if (memory[self.getMemory()]['healing']+memory[self.getMemory()]['overheal']) == 0:
			return 0
		else:
			return memory[self.getMemory()]['overheal']/(memory[self.getMemory()]['overheal'] + memory[self.getMemory()]['healing'])
	
class absorbHealWatch(eventWatch):

	def getEvents(self):
		return 'absorbed'

	def operation(self, event, memory):
		memory[self.getMemory()] += event['amount']

#TODO: get my shit together
class pantsWatch(eventWatch):
	def __init__(self, abilityID = [139, 2050, 2060, 2061, 32546, 208065], baseDuration = 15, talentID = 32546, tolerance = 200, eventType = None, source = 'player', target = None, sentinel = False):
	   super().__init__(abilityID[0], eventType, source, target, sentinel)
	   self.abilityID.extend(abilityID[1:])
	   self.baseDuration = baseDuration * 1000
	   self.basePandemic = self.baseDuration * 0.3
	   self.talentID = talentID
	   self.tolerance = tolerance

	def getEvents(self):
		return ['combatantinfo','applybuff','heal','refreshbuff']

	def memInit(self):
		return {'total':0,
		  'talentStatus':False,
		  'endTime':{},
		  'lastTick':{}}

	def operation(self, event, memory):
		if event['type'] == 'combatantinfo':
			for i in event['talents']:
				if i['id'] == self.talentID:
					memory[self.getMemory()]['talentStatus'] = True
			self.start = event['timestamp']
		else:
			if not event['targetID'] in memory[self.getMemory()]['endTime']:
				memory[self.getMemory()]['endTime'][event['targetID']] = 0
			if not event['targetID'] in memory[self.getMemory()]['lastTick']:
				memory[self.getMemory()]['lastTick'][event['targetID']] = False
		if event['type'] == 'heal':
			if event['ability']['guid'] == self.abilityID[0]:
				if memory[self.getMemory()]['endTime'][event['targetID']] == 0:
					memory[self.getMemory()]['endTime'][event['targetID']] = event['timestamp']
					+ self.baseDuration + self.tolerance
				if event['timestamp'] > memory[self.getMemory()]['endTime'][event['targetID']]:
					print(event['timestamp'] - self.start)
					memory[self.getMemory()]['lastTick'][event['targetID']] = event['timestamp']
					memory[self.getMemory()]['total'] += event['amount']
			elif memory[self.getMemory()]['talentStatus']:
				if event['timestamp'] < memory[self.getMemory()]['endTime'][event['targetID']]:
					haste = memory['hasteWatch']['haste']
					ticks = (6 * haste) // 1
					timeLeft = (3000/haste) * ticks
					memory[self.getMemory()]['endTime'][event['targetID']] = (memory[self.getMemory()]['lastTick'][event['targetID']] + timeLeft + self.tolerance)
		if event['type'] == 'applybuff':
			memory[self.getMemory()]['endTime'][event['targetID']] = event['timestamp'] + self.baseDuration + self.tolerance
		if event['type'] == 'refreshbuff':
			memory[self.getMemory()]['endTime'][event['targetID']] = (event['timestamp'] + self.baseDuration
			+ max(min (memory[self.getMemory()]['endTime'][event['targetID']] - event['timestamp'], self.basePandemic),0)
			+ self.tolerance)
				


	def postOp(self, events, memory):
		return memory[self.getMemory()]['total']

class ERWatch(eventWatch):
	def __init__(self, abilityID = 139, baseDuration = 15, pantsDuration = 21, pantsID = 132447, tolerance = 200, eventType = None, source = 'player', target = None, sentinel = False):
		super().__init__(abilityID, eventType, source, target, sentinel)
		self.pantsID = pantsID
		self.baseDuration = baseDuration * 1000
		self.pantsDuration = pantsDuration * 1000
		self.pantsdemic = 0.3 * self.pantsDuration
		self.basePandemic = 0.3 * self.baseDuration
		self.tolerance = tolerance

	def getEvents(self):
		return ['combatantinfo', 'applybuff', 'heal', 'refreshbuff']

	def memInit(self):
		return {'legendaryEquipped':False,
				'targetTimestamps':{},
				'total': 0}

	def operation(self, event, memory):
		if event['type'] == 'combatantinfo':
			for i in event['gear']:
				if i['id'] == self.pantsID:
					memory[self.getMemory()]['legendaryEquipped'] = True
		else:
			if not event['targetID'] in memory[self.getMemory()]['targetTimestamps'].keys():
				memory[self.getMemory()]['targetTimestamps'][event['targetID']] = event['timestamp']
				+ (self.pantsDuration if memory[self.getMemory()]['legendaryEquipped'] == False else self.baseDuration)
		if event['type'] == 'applybuff':
			memory[self.getMemory()]['targetTimestamps'][event['targetID']] = (event['timestamp'] + self.tolerance
			+ (self.pantsDuration if memory[self.getMemory()]['legendaryEquipped'] else self.baseDuration))
		if event['type'] == 'refreshbuff':
			memory[self.getMemory()]['targetTimestamps'][event['targetID']] = (event['timestamp'] + self.tolerance
			+ (self.pantsDuration if memory[self.getMemory()]['legendaryEquipped'] else self.baseDuration)
			+ max(0,min((memory[self.getMemory()]['targetTimestamps'][event['targetID']] - event['timestamp']), (self.pantsdemic if memory[self.getMemory()]['legendaryEquipped'] else self.basePandemic))))
		if event['type'] == 'heal':
			if event['timestamp'] > memory[self.getMemory()]['targetTimestamps'][event['targetID']]:
				memory[self.getMemory()]['total'] += event['amount']

	def postOp(self, events, memory):
		return memory[self.getMemory()]['total']

	





	
class absorbRawWatch(eventWatch):

	def getEvents(self):
		return ['applybuff', 'applydebuff']

	def operation(self, event, memory):
		memory[self.getMemory()] += event['absorb']

class duration(eventWatch):
	def getEvents(self):
		return []

	def postOp(self, events, memory):
		return (events[len(events)-1]['timestamp'] - events[0]['timestamp'])/1000

class absorbOverhealWatch(eventWatch):

	def getEvents(self):
		return ['absorbed', 'applybuff', 'applydebuff']

	def memInit(self):
		return {'healing':0, 'raw':0}
		
	def operation(self, event, memory):
		if event['type'] == 'absorbed':
			memory[self.getMemory()]['healing'] += event['amount']
		elif event['type'] == 'applybuff' or event['type'] == 'applydebuff':
			memory[self.getMemory()]['raw'] += event['absorb']

	def postOp(self, events, memory):
		if memory[self.getMemory()]['raw'] == 0:
			#crotchbomb again
			return 0
		else:
			return 1 - memory[self.getMemory()]['healing']/memory[self.getMemory()]['raw']

class auraStartWatch(eventWatch):

	def getEvents(self):
		return ['combatantinfo', 'applybuff', 'refreshbuff','refreshdebuff','applydebuff','removedebuff','removebuff']

	def operation(self, event, memory):
		if event['type'] == 'combatantinfo':
			for i in event['auras']:
				if i['ability'] == self.abilityID[0]:
					memory[self.getMemory()] = True
		elif event['type'] == 'applybuff' or 'applydebuff' and memory[self.getMemory()] != None and not memory[self.getMemory()]:
			memory[self.getMemory()] = False
		else:
			memory[self.getMemory()] = True

	def postOp(self, events, memory):
		return not not memory[self.getMemory()]

	def memInit(self):
		return None

def specToID(playerClass, playerSpec):
	specs = {'blood':1,
			 'frost':2,
			 'unholy':3,'balance':1,'feral':2,'guardian':3, 'restoration':4, 'beast mastery':1, 'marksmanship':2,
			 'survival':3, 'arcane':1, 'fire':2, 'frost':3, 'brewmaster':1, 'mistweaver':2, 'windwalker':3, 'holy':1,
			 'protection':2, 'retribution':3, 'discipline':1, 'shadow':3, 'assassination':1, 'combat':2, 'subtlety':3,
			 'outlaw':4, 'elemental':1, 'enhancement':2, 'affliction':1, 'demonology':2, 'destruction':3,
			 'arms':1, 'fury':2, 'gladiator':4, 'havoc':1, 'vengeance':2}
	if playerSpec == 'holy' or playerSpec == 'protection' or playerSpec == 'restoration':
		if playerClass == 7:
			return 2
		elif playerClass == 11:
			return 3
		elif playerClass == 9:
			return 3
	else:
		return specs[playerSpec]
class dateFilter():
	def __init__(self, lowerDate, upperDate):
		#translation of date to ms since epoch
		self.lowerBound = str(int(datetime.datetime(lowerDate.year, lowerDate.month, lowerDate.day).timestamp() * 1000))
		self.upperBound = str(int(datetime.datetime(upperDate.year, upperDate.month, upperDate.day).timestamp() * 1000))
		self.lowerDateTimestamp = lowerDate.timestamp()*1000
		self.upperDateTimestamp = upperDate.timestamp()*1000
		
class itemFilter():
	def __init__(self, itemID):
		self.itemID = []
		if type(itemID) is list:
			self.itemID.extend(itemID)
		elif type(itemID) is int:
			self.itemID.append(itemID)
		else:
			raise TypeError("itemID must be an int or a list of ints")

def gearFromRankings(rank):
	gearStr = ""
	for i in rank['gear']:
		gearStr += str(i['id']) + " "
	return gearStr[:-1]

def talentsFromRankings(rank):
	talentStr = ""
	for i in rank['talents']:
		talentStr += str(i['id']) + " "
	return talentStr[:-1]

def eventParse(events, eventWatchList, actorID):
	if len(events) == 0:
		return
	watchedEvents = {}
	memory = {}
	for event in eventWatchList:
		memory[event.getMemory()] = event.memInit()
	for event in events:
		for watched in eventWatchList:
			#if ((event['type'] == 'combatantinfo' or ('ability' in event.keys() and
			#	event['ability']['guid'] in watched.abilityID)) and event['type'] in watched.getEvents() and
			#	(not watched.source or (watched.source == "player" and event['sourceID'] == actorID)
			#	 or (watched.source == "other" and event['sourceID'] != actorID)) and
			#	(not watched.target or (watched.target == "player" and event['targetID'] == actorID)
			#	 or watched.target == "other" and event['targetID'] != actorID)):
			if ((event['type'] in watched.getEvents() and (event['type'] == 'combatantinfo' or event['ability']['guid'] in watched.abilityID)) 
			and (event['type'] == 'combatantinfo' or ((not watched.source or (watched.source == "player" and event['sourceID'] == actorID) or 
			(watched.source == "other" and event['sourceID'] != actorID)) and (not watched.target or (watched.target == "player" and 
			event['targetID'] == actorID) or (watched.target == "other" and event['targetID'] != actorID))))):
				watched.operation(event, memory)
	results = []
	for watched in eventWatchList:
		results.append(watched.postOp(events, memory))
	return results

		

class abilityFilter():
	def __init__(self, abilityID):
		self.abilityID = []
		if type(abilityID) is list:
			self.abilityID.extend(abilityID)
		elif type(abilityID) is int:
			self.abilityID.append(abilityID)
		else:
			raise TypeError("abilityID must be an int or a list of ints")

def wclRequest(url):
	url += '&api_key=' + api_key
	response = requests.get(url)
	if not 'application/json' in response.headers['content-type']:
		if response.headers['content-type'] == 'text/html; charset=UTF-8':
			return wclRequest(url)
	while response.status_code == 429:
		time.sleep(1)
		response = requests.get(url)
	return response.json()

def fightsInfo(rankingsEntry):
	response = wclRequest('https://www.warcraftlogs.com:443/v1/report/fights/'
						  +rankingsEntry['reportID']+'?translate=true')
	actorID = None
	if not 'friendlies' in response.keys():
		return None
	for i in response['friendlies']:
			if i['name'] == rankingsEntry['name']:
				actorID = i['id']
				break
	if actorID == None:
		return None
	fightCache[rankingsEntry['reportID']] = response
	return (response['fights'][rankingsEntry['fightID']-1]['start_time'], response['fights'][rankingsEntry['fightID']-1]['end_time'], actorID)
	
def eventsFromRankings(rankingsEntry, filterString = None, filterActor = True):
	if rankingsEntry['reportID'] in fightCache.keys():
		for i in fightCache[rankingsEntry['reportID']]['friendlies']:
			if i['name'] == rankingsEntry['name']:
				actorID = i['id']
				break
		fightInfo = (fightCache[rankingsEntry['reportID']]['fights'][rankingsEntry['fightID']-1]['start_time'],
				 fightCache[rankingsEntry['reportID']]['fights'][rankingsEntry['fightID']-1]['end_time'],
				 actorID)
	else:
		fightInfo = fightsInfo(rankingsEntry)
		if fightInfo == None:
			return None
	request = wclRequest('https://www.warcraftlogs.com:443/v1/report/events/'
						+ rankingsEntry['reportID'] +'?start='
						+ str(fightInfo[0]) +'&end='
						+ str(fightInfo[1]) +
						('&actorid=' + str(int(fightInfo[2])) if filterActor == True else '')
					   +'&translate=true')['events']
	return request, fightInfo[2]

def generateRankings(filterList = [], encounterID = all_bosses, limit = 200, metric = 'hps', difficulty = 5, partition = 1,
					 playerClass = None, playerSpec = None, limitType = 'all', guild = None,
					 region = None):
	if type(encounterID) is int:
		#this is sort of hacky, but makes it easier to use a for loop to parse multiple bosses
		encounterID = [encounterID]
	baseRequest = "https://www.warcraftlogs.com:443/v1/rankings/encounter/"
	requestParams = "?translate=true&"
	if type(difficulty) is int:
		#see above note about encounterID
		difficulty = [difficulty]
	difficulty = [diff if type(diff) is int else difficulties[diff] for diff in difficulty]
	requestParams += "limit=" + str(limit) + "&"
	requestParams += "metric=" + metric + "&"
	requestParams += "partition=" + str(partition) + "&"
	if len(filterList) > 0:
		requestParams += "filter="
	for i in filterList:
		if type(i) is dateFilter:
			requestParams += "date." + i.lowerBound + "." + i.upperBound
		if type(i) is itemFilter:
			requestParams += "items"
			for j in i.itemID:
				requestParams += "." + str(j)
		if type(i) is abilityFilter:
			requestParams += "abilities"
			for j in i.abilityID:
				requestParams += "." + str(j)
		requestParams += '%7C'
	if requestParams[-3:] == '%7C':
		requestParams = requestParams[:-3]
	#theres gotta be a better way of doing this
	if requestParams[-1] != "&":
		requestParams += "&"
	if playerClass != None:
		if type(playerClass) is str:
			playerClass = classes[playerClass]
		requestParams += "class="+str(playerClass)+"&"
	if playerSpec != None:
		if type(playerSpec) is str:
			playerSpec = specToID(playerClass, playerSpec)
		requestParams += "spec="+str(playerSpec)+"&"
	if region != None:
		requestParams += "region="+region+"&"
	if guild != None:
		requestParams += "guild="+guild+"&"
	allRankings = []
	for diff in difficulty:
		for encID in encounterID:
			allRankings.extend(wclRequest(baseRequest+str(encID)+requestParams+"difficulty="+str(diff))['rankings'])
	if limitType == 'top':
		allRankings = sorted(allRankings, reverse = True, key = lambda r: r['total'])[:limit]
	for i in filterList:
		if type(i) is dateFilter:
		   allRankings = [x for x in allRankings if x['startTime'] > i.lowerDateTimestamp and x['startTime'] < i.upperDateTimestamp]
	return [x for x in allRankings if x['name'] != "Anonymous"]
