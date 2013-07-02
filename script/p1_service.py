#
# P1 reader
# 

import datetime
import json
import logging
import serial
import signal
import sys


# Constants
script_version = "1.2.0"
script_date = "2013-06-30"

keepRunning = True
data = {}


# Main program
def main():
	global keepRunning, data

	def signal_handler(signal, frame):
		global keepRunning
		logger.info('Signal received: %s' % signal)
		logger.info('Setting keepRunning to False')
		keepRunning = False
	
	signal.signal(signal.SIGINT, signal_handler)


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

	# set up logging
	logger = logging.getLogger('p1service')
	hdlr = logging.FileHandler('/mnt/p1tmpfs/log/p1.log')
	formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
	hdlr.setFormatter(formatter)
	logger.addHandler(hdlr) 
	#logger.setLevel(logging.INFO)
	logger.setLevel(logging.DEBUG)

	logger.info("P1 reader, v%s, %s" % (script_version, script_date))
	
	# Try to read from file
	try:
		logger.info('Trying to read from file')
		with open('/mnt/p1tmpfs/data/data_0.json', 'r') as fDataIn:
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
		#data['gasHourlyTotalist'] = [None] * 25
		data['eLastHourList'] = [None] * 360

		datetimeNow = datetime.datetime.now()
		currentDay = datetimeNow.isoweekday()
		currentHour = datetimeNow.hour
		data['eHourlyMinList'][currentHour] = sys.maxint
		data['eHourlyMaxList'][currentHour] = 0
	else:
		datetimeFromFile = datetime.datetime.strptime(data['timestamp'], '%Y-%m-%d %H:%M:%S')
		currentDay = datetimeFromFile.day
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
	aLine = ''
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
	logger.info('Data alignment done')

	while keepRunning:
		i=0
		linesFromP1=[]
		aLine=''
	
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
				
			# calculate derived values
			eTotal = eTotalOffPeak + eTotalPeak
			data['timestamp'] = datetimeNow.strftime("%Y-%m-%d %H:%M:%S")
			data['eNow'] = eNow
			data['eTotal'] = eTotal
			data['eTotalOffPeak'] = eTotalOffPeak
			data['eTotalPeak'] = eTotalPeak
			if (gasTotal != 0):
				data['gasTotal'] = gasTotal
			data['eLastHourList'].pop(0)
			data['eLastHourList'].append(eNow)
			
			# check day change
			if (datetimeNow.isoweekday() != currentDay):
				# set the 25th entry in the eHourlyTotalList
				data['eHourlyTotalList'][24] = eTotal
				# write the structure to disk
				dayFileName = '/mnt/p1tmpfs/data/data_' + str(currentDay) + '.json'
				logger.info('Writing daily results to %s' % dayFileName)
				with open(dayFileName, 'w') as fDataDay:
					p1DataJsonText = json.dumps(data)
					fDataDay.write(p1DataJsonText)

				data['eHourlyMinList'] = [None] * 24
				data['eHourlyMaxList'] = [None] * 24
				data['eHourlyTotalList'] = [None] * 25
				data['eDayMin'] = sys.maxint
				data['eDayMax'] = 0
				currentDay = datetimeNow.isoweekday()
			
			# check hour change	
			if (datetimeNow.hour == currentHour):
				data['eHourlyMinList'][currentHour] = min(data['eHourlyMinList'][currentHour], eNow)
				data['eHourlyMaxList'][currentHour] = max(data['eHourlyMaxList'][currentHour], eNow)
			else:
				currentHour = datetimeNow.hour
				data['eHourlyMinList'][currentHour] = eNow
				data['eHourlyMaxList'][currentHour] = eNow
				data['eHourlyTotalList'][currentHour] = eTotal

			data['eDayMin'] = min(data['eDayMin'], eNow)
			data['eDayMax'] = max(data['eDayMax'], eNow)

			if (gasTotal != 0):
				logger.debug("(e_nu, e_dal, e_piek, gas) = (%4.0f, %.0f, %.0f, %.0f)" % (eNow, eTotalOffPeak, eTotalPeak, gasTotal))
			else:
				logger.debug("(e_nu, e_dal, e_piek) = (%4.0f, %.0f, %.0f)" % (eNow, eTotalOffPeak, eTotalPeak))
	
			# now write the json file
			with open('/mnt/p1tmpfs/data/data_0.json', 'w') as fData:
				p1DataJsonText = json.dumps(data)
				fData.write(p1DataJsonText)
		else:
			logger.info('Stopping the loop')		
	
	logger.info('P1 reader stopped successfully. Have a nice day!')
	
	
if __name__ == '__main__':
    main()
