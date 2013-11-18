#!/usr/bin/python

#
# SmartmeterEasy
# 

import ConfigParser
import datetime
import json
import logging
import os
import serial
import shutil
import signal
import sys

# Constants
script_version = "1.5.0"
script_date = "2013-11-17"

DATA_NOW_FILENAME = 'data_0_0.json'
DATA_P1_FILENAME = 'p1.json'
LOG_FILENAME = 'smartmeterEasy.log'


keepRunning = True
data = {}
dataP1 = {}


# Main program
def main():
	global keepRunning, data

	def signal_handler(signal, frame):
		global keepRunning
		logger.info('Signal received: %s' % signal)
		logger.info('Setting keepRunning to False')
		keepRunning = False
	
	signal.signal(signal.SIGINT, signal_handler)
	signal.signal(signal.SIGTERM, signal_handler)


	#Set COM port config
	ser = serial.Serial()
	ser.baudrate = 9600
	ser.bytesize=serial.SEVENBITS
	ser.parity=serial.PARITY_EVEN
	ser.stopbits=serial.STOPBITS_ONE
	ser.xonxoff=0
	ser.rtscts=0
	ser.timeout=20
	ser.port="/dev/ttyUSB0"
	
	# Initialisation
	config = ConfigParser.SafeConfigParser()
	for loc in os.curdir, os.path.expanduser("~"), "/etc/smartmeterEasy":
		try: 
			with open(os.path.join(loc,"smartmeterEasy.conf")) as source:
				config.readfp(source)
		except IOError:
			pass

	# set up logging
	logDir = config.get('GENERAL', 'log_dir')
	if not os.path.exists(logDir):
		os.makedirs(logDir)
	logger = logging.getLogger('smartmeterEasy')
	logFile = logDir + '/' + LOG_FILENAME
	hdlr = logging.FileHandler(logFile)
	formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
	hdlr.setFormatter(formatter)
	logger.addHandler(hdlr) 
	logger.setLevel(logging.INFO)
	#logger.setLevel(logging.DEBUG)
	
	mainDataDir = config.get('GENERAL', 'main_data_dir')
	backupMainDataDir = config.get('GENERAL', 'backup_main_data_dir')
	dailyDataDir = config.get('GENERAL', 'daily_data_dir')
	writePrimaryValuesToFile = config.getboolean('GENERAL', 'write_primary_values_to_file')

	logger.info("---")
	logger.info("SmartmeterEasy, v%s, %s" % (script_version, script_date))
	logger.info("Configuration:")
	logger.info("  Log directory: %s" % logDir) 
	logger.info("  Main data directory: %s" % mainDataDir) 
	logger.info("  Daily data directory: %s" % dailyDataDir) 
	logger.info("  Backup main data directory: %s" % backupMainDataDir) 
	logger.info("  Write primary values to file: %s" % writePrimaryValuesToFile)
	
	if not os.path.exists(mainDataDir):
		if os.path.exists(backupMainDataDir):
			logger.info("Restoring main data dir from %s" % backupMainDataDir)
			shutil.copytree(backupMainDataDir, mainDataDir)
		else:
			logger.info("Creating main data dir %s" % mainDataDir)
			os.makedirs(mainDataDir)
	if not os.path.exists(dailyDataDir):
		os.makedirs(dailyDataDir)
	dataNowFilePath = mainDataDir + '/' + DATA_NOW_FILENAME
	dataP1FilePath = mainDataDir + '/' + DATA_P1_FILENAME

	
	# Try to read from file
	try:
		logger.info('Trying to read from file')
		with open(dataNowFilePath, 'r') as fDataIn:
			data = json.load(fDataIn)
			logger.info('Using data from file dated %s' % data['timestamp'])
	except IOError:
		logger.warning('No previous data file found. Creating new and empty data set.')

	if (len(data) == 0):
		data['timestamp'] = None
		data['eNow'] = None
		data['eDayMin'] = sys.maxint
		data['eDayMax'] = 0
		data['eTotal'] = 0
		data['eTotalOffPeak'] = 0
		data['eTotalPeak'] = 0
		data['eHourlyMinList'] = [None] * 24
		data['eHourlyMaxList'] = [None] * 24
		data['eHourlyTotalList'] = [None] * 25
		data['eLastHourList'] = [None] * 360
		# Note: gas will be created if needed

		datetimeNow = datetime.datetime.now()
		currentDay = datetimeNow.isoweekday()
		currentHour = datetimeNow.hour
		data['eHourlyMinList'][currentHour] = sys.maxint
		data['eHourlyMaxList'][currentHour] = 0
	else:
		datetimeFromFile = datetime.datetime.strptime(data['timestamp'], '%Y-%m-%d %H:%M:%S')
		currentDay = datetimeFromFile.isoweekday()
		currentHour = datetimeFromFile.hour
		if 'eHourlyTotalList' in data:
			logger.debug('eHourlyTotalList already exists')
		else:
			logger.debug('Creating eHourlyTotalList')
			data['eHourlyTotalList'] = [None] * 25
	
	
	#Open COM port
	try:
		ser.open()
	except:
		sys.exit("Error while opening %s. Program aborted." % ser.name)      


	# do first loop to make sure we are aligned
	logger.info('Reading COM port to align data (should take less then 10 seconds) ...')
	firstLine = True
	aLine = ''
	gasPresent = None
	while (aLine != "!" and keepRunning):
		try:
			lineRaw = ser.readline()
		except:
			if keepRunning:
				logger.error("Unable to read from COM port %s. Program aborted." % ser.name)
			else:
				logger.info('Reading from COM port has been cancelled')
		
		if keepRunning:
			aLine=str(lineRaw).strip()
			logger.info('Output from COM port: %s' % aLine)
			if firstLine:
				if (aLine[0] == '/' and aLine[4] == '5'):
					logger.info('Data alignment done')
					logger.info('Checking for gas ...')
					gasPresent = False
				firstLine = False
			else:
				if (aLine[0:10] == "0-1:24.3.0"):
					gasPresent = True

	if (gasPresent == None and keepRunning):
		# do an additional loop to check for gas
		logger.info('Checking for gas (should take about 10 seconds) ...')
		gasPresent = False
		while (aLine != "!"):
			try:
				lineRaw = ser.readline()
			except:
				if keepRunning:
					logger.error("Unable to read from COM port %s. Program aborted." % ser.name)
				else:
					logger.info('Reading from COM port has been cancelled')
			aLine=str(lineRaw).strip()
			logger.info('Output from COM port: %s' % aLine)
			if (aLine[0:10] == "0-1:24.3.0"):
				gasPresent = True
		
	if (gasPresent == True):
		logger.info('Gas is present')
		if not 'gasHourlyTotalList' in data:
			data['gasHourlyTotalList'] = [None] * 25
	else:
		logger.info('Gas is not present')
			

	while keepRunning:
		i=0
		linesFromP1=[]
		aLine=''
		gasTotal = 0
	
		# now read all data from one session
		if keepRunning:
			while (aLine != "!"):
				try:
					lineRaw = ser.readline()
				except:
					if keepRunning:
						logger.error("Unable to read from COM port %s. Program aborted." % ser.name)
					else:
						logger.info('Reading from COM port has been cancelled')
				aLine=str(lineRaw).strip()
				linesFromP1.append(aLine)
			
		if keepRunning:	
			datetimeNow = datetime.datetime.now()
			i = 0
			while i < len(linesFromP1):
				if linesFromP1[i][0:9] == "1-0:1.8.1":
					eTotalOffPeak = int(float(linesFromP1[i][10:19]) * 1000)
				elif linesFromP1[i][0:9] == "1-0:1.8.2":
					eTotalPeak = int(float(linesFromP1[i][10:19]) * 1000)
				elif linesFromP1[i][0:9] == "1-0:1.7.0":
					eNow = int(float(linesFromP1[i][10:17]) * 1000)
				elif linesFromP1[i][0:10] == "0-1:24.3.0":
					gasTotal = int(float(linesFromP1[i + 1][1:10]) * 1000)
				i = i + 1
				
			# set dataP1 values
			if writePrimaryValuesToFile:
				dataP1['timestamp'] = datetimeNow.strftime("%Y-%m-%d %H:%M:%S")
				dataP1['eNow'] = eNow
				dataP1['eTotalOffPeak'] = eTotalOffPeak
				dataP1['eTotalPeak'] = eTotalPeak
				if (gasPresent):
					dataP1['gasTotal'] = gasTotal
			
			# calculate derived values
			eTotal = eTotalOffPeak + eTotalPeak
			data['eNow'] = eNow
			data['eTotal'] = eTotal
			data['eTotalOffPeak'] = eTotalOffPeak
			data['eTotalPeak'] = eTotalPeak
			if (gasPresent):
				data['gasTotal'] = gasTotal
			data['eLastHourList'].pop(0)
			data['eLastHourList'].append(eNow)
			
			# check hour change	
			if (datetimeNow.hour == currentHour):
				if (data['eHourlyMinList'][currentHour] is None):
					data['eHourlyMinList'][currentHour] = eNow
				else:
					data['eHourlyMinList'][currentHour] = min(data['eHourlyMinList'][currentHour], eNow)
				data['eHourlyMaxList'][currentHour] = max(data['eHourlyMaxList'][currentHour], eNow)
			else:
				if (datetimeNow.isoweekday() != currentDay):
					# set the 25th entry in the eHourlyTotalList
					data['eHourlyTotalList'][24] = eTotal
					if (gasPresent):
						data['gasHourlyTotalList'][24] = gasTotal
				
				# write the structure to disk
				hourFileName = mainDataDir + '/data_' + str(currentDay) + '_' + str(currentHour + 1) + '.json'
				logger.info('Writing hourly results to %s' % hourFileName)
				with open(hourFileName, 'w') as fDataHour:
					p1DataJsonText = json.dumps(data, sort_keys=True)
					fDataHour.write(p1DataJsonText)
					
				# if the currentHour is 23, it means this is also the daily change
				if (currentHour == 23):
					dataDay = data.copy()
					dataDay.pop("eLastHourList", None)
					yesterday = datetimeNow - datetime.timedelta(days=1)
					dailyFileName = dailyDataDir + '/data_' + yesterday.strftime("%Y_%m_%d") + '.json'
					logger.info('Writing daily results to %s' % dailyFileName)
					with open(dailyFileName, 'w') as fDataDay:
						p1DataDayJsonText = json.dumps(dataDay, sort_keys=True)
						fDataDay.write(p1DataDayJsonText)
					
					
				# check also for a day change; if so, then reset stuff
				if (datetimeNow.isoweekday() != currentDay):
					data['eHourlyMinList'] = [None] * 24
					data['eHourlyMaxList'] = [None] * 24
					data['eHourlyTotalList'] = [None] * 25
					if (gasPresent):
						data['gasHourlyTotalList'] = [None] * 25
					data['eDayMin'] = eNow
					data['eDayMax'] = eNow
					currentDay = datetimeNow.isoweekday()

				currentHour = datetimeNow.hour
				data['eHourlyMinList'][currentHour] = eNow
				data['eHourlyMaxList'][currentHour] = eNow
				data['eHourlyTotalList'][currentHour] = eTotal
				if (gasPresent):
					data['gasHourlyTotalList'][currentHour] = gasTotal

			data['eDayMin'] = min(data['eDayMin'], eNow)
			data['eDayMax'] = max(data['eDayMax'], eNow)
			data['timestamp'] = datetimeNow.strftime("%Y-%m-%d %H:%M:%S")

			if (gasPresent):
				logger.debug("(e_nu, e_dal, e_piek, gas) = (%4.0f, %.0f, %.0f, %.0f)" % (eNow, eTotalOffPeak, eTotalPeak, gasTotal))
			else:
				logger.debug("(e_nu, e_dal, e_piek) = (%4.0f, %.0f, %.0f)" % (eNow, eTotalOffPeak, eTotalPeak))
	
			if writePrimaryValuesToFile:
				# now write the json file with primary values
				with open(dataP1FilePath, 'w') as fDataP1:
					dataP1JsonText = json.dumps(dataP1, sort_keys=True)
					fDataP1.write(dataP1JsonText)
				
			# now write the json file
			with open(dataNowFilePath, 'w') as fData:
				p1DataJsonText = json.dumps(data, sort_keys=True)
				fData.write(p1DataJsonText)
		else:
			logger.info('Stopping the loop')		
	
	logger.info('SmartmeterEasy stopped successfully. Have a nice day!')
	
	
if __name__ == '__main__':
    main()
