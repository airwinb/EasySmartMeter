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
import time

# Constants
script_version = "1.6.0"
script_date = "2014-01-24"

DATA_NOW_FILENAME = 'data_0_0.json'
DATA_P1_FILENAME = 'p1.json'
LOG_FILENAME = 'smartmeterEasy.log'

MAX_LINES_NEEDED_FOR_ALIGNMENT = 60
MAX_ALIGNMENT_ATTEMPTS = 10
ALIGNMENT_LINE = "!"
SLEEP_BETWEEN_ALIGNMENT_ATTEMPTS = 1.5

keep_running = True
data = {}
data_p1 = {}


# Main program
def main():
    global keep_running, data

    def signal_handler(signal, frame):
        global keep_running
        logger.info('Signal received: %s' % signal)
        logger.info('Setting keepRunning to False')
        keep_running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    #Set COM port config
    ser = serial.Serial()
    ser.baudrate = 9600
    ser.bytesize = serial.SEVENBITS
    ser.parity = serial.PARITY_EVEN
    ser.stopbits = serial.STOPBITS_ONE
    ser.xonxoff = 0
    ser.rtscts = 0
    ser.timeout = 20
    ser.port = "/dev/ttyUSB0"

    # Initialisation
    config = ConfigParser.SafeConfigParser()
    for loc in os.curdir, os.path.expanduser("~"), "/etc/smartmeterEasy":
        try:
            with open(os.path.join(loc, "smartmeterEasy.conf")) as source:
                config.readfp(source)
        except IOError:
            pass

    # set up logging
    log_dir = config.get('GENERAL', 'log_dir')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    logger = logging.getLogger('smartmeterEasy')
    log_file = log_dir + '/' + LOG_FILENAME
    log_handle = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    log_handle.setFormatter(formatter)
    logger.addHandler(log_handle)
    logger.setLevel(logging.INFO)
    #logger.setLevel(logging.DEBUG)

    main_data_dir = config.get('GENERAL', 'main_data_dir')
    backup_main_data_dir = config.get('GENERAL', 'backup_main_data_dir')
    daily_data_dir = config.get('GENERAL', 'daily_data_dir')
    write_primary_values_to_file = config.getboolean('GENERAL', 'write_primary_values_to_file')

    logger.info("---")
    logger.info("SmartmeterEasy, v%s, %s" % (script_version, script_date))
    logger.info("Configuration:")
    logger.info("  Log directory: %s" % log_dir)
    logger.info("  Main data directory: %s" % main_data_dir)
    logger.info("  Daily data directory: %s" % daily_data_dir)
    logger.info("  Backup main data directory: %s" % backup_main_data_dir)
    logger.info("  Write primary values to file: %s" % write_primary_values_to_file)

    if not os.path.exists(main_data_dir):
        if os.path.exists(backup_main_data_dir):
            logger.info("Restoring main data dir from %s" % backup_main_data_dir)
            shutil.copytree(backup_main_data_dir, main_data_dir)
        else:
            logger.info("Creating main data dir %s" % main_data_dir)
            os.makedirs(main_data_dir)
    if not os.path.exists(daily_data_dir):
        os.makedirs(daily_data_dir)
    data_now_file_path = main_data_dir + '/' + DATA_NOW_FILENAME
    data_p1_file_path = main_data_dir + '/' + DATA_P1_FILENAME

    # Try to read from file
    try:
        logger.info('Trying to read from file')
        with open(data_now_file_path, 'r') as fDataIn:
            data = json.load(fDataIn)
            logger.info('Using data from file dated %s' % data['timestamp'])
    except IOError:
        logger.warning('No previous data file found. Creating new and empty data set.')

    if len(data) == 0:
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

        datetime_now = datetime.datetime.now()
        current_day = datetime_now.isoweekday()
        current_hour = datetime_now.hour
        data['eHourlyMinList'][current_hour] = sys.maxint
        data['eHourlyMaxList'][current_hour] = 0
    else:
        datetime_from_file = datetime.datetime.strptime(data['timestamp'], '%Y-%m-%d %H:%M:%S')
        current_day = datetime_from_file.isoweekday()
        current_hour = datetime_from_file.hour
        if 'eHourlyTotalList' in data:
            logger.info('eHourlyTotalList already exists')
        else:
            logger.info('Creating eHourlyTotalList')
            data['eHourlyTotalList'] = [None] * 25

    #Open COM port
    try:
        logger.info("Opening COM port %s" % ser.name)
        ser.open()
    except:
        sys.exit("Error while opening %s. Program aborted." % ser.name)

    # do first loop to make sure we are aligned
    # since alignment fails with some people because it never reads the "!", we try to
    # open and close the COM port a few times
    logger.info('Reading COM port to align data (should take less then 10 seconds) ...')
    aligned = False
    a_line = ''
    gas_present = False
    i = 0
    j = 1
    while not aligned and i < MAX_LINES_NEEDED_FOR_ALIGNMENT and j <= MAX_ALIGNMENT_ATTEMPTS and keep_running:
        line_raw = ''
        if i == 0:
            logger.info("Starting alignment attempt %d ..." % j)
        try:
            line_raw = ser.readline()
            i += 1
        except:
            if keep_running:
                logger.error("Unable to read from COM port %s. Program aborted." % ser.name)
            else:
                logger.info('Reading from COM port has been cancelled')

        if keep_running:
            a_line = str(line_raw).strip()
            logger.info('Output from COM port: %s' % a_line)
            if a_line == ALIGNMENT_LINE:
                aligned = True
            elif a_line[0:10] == "0-1:24.3.0":
                gas_present = True
            if i >= MAX_LINES_NEEDED_FOR_ALIGNMENT:
                logger.warning("Alignment attempt %d has failed" % j)
                try:
                    logger.info("Closing COM port %s" % ser.name)
                    ser.close()
                except:
                    logger.error("Unable to close COM port %s." % ser.name)
                j += 1
                i = 0
                if j <= MAX_ALIGNMENT_ATTEMPTS:
                    logger.info("Sleeping %0.1f seconds ..." % SLEEP_BETWEEN_ALIGNMENT_ATTEMPTS)
                    time.sleep(SLEEP_BETWEEN_ALIGNMENT_ATTEMPTS)
                    try:
                        logger.info("Opening COM port %s" % ser.name)
                        ser.open()
                    except:
                        sys.exit("Error while opening %s. Program aborted." % ser.name)
                else:
                    logger.error("Unable to align data from smartmeter after %d attempts. Aborting program." % MAX_ALIGNMENT_ATTEMPTS)
                    sys.exit("Unable to align data from smartmeter after %d attempts. Aborting program." % MAX_ALIGNMENT_ATTEMPTS)

    if aligned:
        logger.info("Alignment done!")

    if gas_present is None and keep_running:
        # do an additional loop to check for gas
        logger.info('Checking for gas (should take about 10 seconds) ...')
        gas_present = False
        while a_line != ALIGNMENT_LINE:
            line_raw = ''
            try:
                line_raw = ser.readline()
            except:
                if keep_running:
                    logger.error("Unable to read from COM port %s. Program aborted." % ser.name)
                else:
                    logger.info('Reading from COM port has been cancelled')
            a_line = str(line_raw).strip()
            logger.info('Output from COM port: %s' % a_line)
            if a_line[0:10] == "0-1:24.3.0":
                gas_present = True

    if gas_present == True:
        logger.info('Gas is present')
        if not 'gasHourlyTotalList' in data:
            data['gasHourlyTotalList'] = [None] * 25
    else:
        logger.info('Gas is not present')

    logger.info("Starting regular readings ...")
    while keep_running:
        lines_from_p1 = []
        a_line = ''
        gas_total = 0

        # now read all data from one session
        if keep_running:
            while a_line != "!":
                line_raw = ''
                try:
                    line_raw = ser.readline()
                except:
                    if keep_running:
                        logger.error("Unable to read from COM port %s. Program aborted." % ser.name)
                    else:
                        logger.info('Reading from COM port has been cancelled')
                a_line = str(line_raw).strip()
                lines_from_p1.append(a_line)

        if keep_running:
            datetime_now = datetime.datetime.now()
            i = 0
            while i < len(lines_from_p1):
                if lines_from_p1[i][0:9] == "1-0:1.8.1":
                    e_total_offpeak = int(float(lines_from_p1[i][10:19]) * 1000)
                elif lines_from_p1[i][0:9] == "1-0:1.8.2":
                    e_total_peak = int(float(lines_from_p1[i][10:19]) * 1000)
                elif lines_from_p1[i][0:9] == "1-0:1.7.0":
                    e_now = int(float(lines_from_p1[i][10:17]) * 1000)
                elif lines_from_p1[i][0:10] == "0-1:24.3.0":
                    gas_total = int(float(lines_from_p1[i + 1][1:10]) * 1000)
                i += 1

            # set dataP1 values
            if write_primary_values_to_file:
                data_p1['timestamp'] = datetime_now.strftime("%Y-%m-%d %H:%M:%S")
                data_p1['eNow'] = e_now
                data_p1['eTotalOffPeak'] = e_total_offpeak
                data_p1['eTotalPeak'] = e_total_peak
                if gas_present:
                    data_p1['gasTotal'] = gas_total

            # calculate derived values
            e_total = e_total_offpeak + e_total_peak
            data['eNow'] = e_now
            data['eTotal'] = e_total
            data['eTotalOffPeak'] = e_total_offpeak
            data['eTotalPeak'] = e_total_peak
            if gas_present:
                data['gasTotal'] = gas_total
            data['eLastHourList'].pop(0)
            data['eLastHourList'].append(e_now)

            # check hour change
            if datetime_now.hour == current_hour:
                if data['eHourlyMinList'][current_hour] is None:
                    data['eHourlyMinList'][current_hour] = e_now
                else:
                    data['eHourlyMinList'][current_hour] = min(data['eHourlyMinList'][current_hour], e_now)
                data['eHourlyMaxList'][current_hour] = max(data['eHourlyMaxList'][current_hour], e_now)
            else:
                if datetime_now.isoweekday() != current_day:
                    # set the 25th entry in the eHourlyTotalList
                    data['eHourlyTotalList'][24] = e_total
                    if gas_present:
                        data['gasHourlyTotalList'][24] = gas_total

                # write the structure to disk
                hour_file_name = main_data_dir + '/data_' + str(current_day) + '_' + str(current_hour + 1) + '.json'
                logger.info('Writing hourly results to %s' % hour_file_name)
                with open(hour_file_name, 'w') as fdata_hour:
                    p1_data_json_text = json.dumps(data, sort_keys=True)
                    fdata_hour.write(p1_data_json_text)

                # if the currentHour is 23, it means this is also the daily change
                if current_hour == 23:
                    data_day = data.copy()
                    data_day.pop("eLastHourList", None)
                    yesterday = datetime_now - datetime.timedelta(days=1)
                    daily_file_name = daily_data_dir + '/data_' + yesterday.strftime("%Y_%m_%d") + '.json'
                    logger.info('Writing daily results to %s' % daily_file_name)
                    with open(daily_file_name, 'w') as fdata_day:
                        p1_data_day_json_text = json.dumps(data_day, sort_keys=True)
                        fdata_day.write(p1_data_day_json_text)

                # check also for a day change; if so, then reset stuff
                if datetime_now.isoweekday() != current_day:
                    data['eHourlyMinList'] = [None] * 24
                    data['eHourlyMaxList'] = [None] * 24
                    data['eHourlyTotalList'] = [None] * 25
                    if gas_present:
                        data['gasHourlyTotalList'] = [None] * 25
                    data['eDayMin'] = e_now
                    data['eDayMax'] = e_now
                    current_day = datetime_now.isoweekday()

                current_hour = datetime_now.hour
                data['eHourlyMinList'][current_hour] = e_now
                data['eHourlyMaxList'][current_hour] = e_now
                data['eHourlyTotalList'][current_hour] = e_total
                if gas_present:
                    data['gasHourlyTotalList'][current_hour] = gas_total

            data['eDayMin'] = min(data['eDayMin'], e_now)
            data['eDayMax'] = max(data['eDayMax'], e_now)
            data['timestamp'] = datetime_now.strftime("%Y-%m-%d %H:%M:%S")

            if gas_present:
                logger.debug("(e_nu, e_dal, e_piek, gas) = (%4.0f, %.0f, %.0f, %.0f)" % (
                    e_now, e_total_offpeak, e_total_peak, gas_total))
            else:
                logger.debug("(e_nu, e_dal, e_piek) = (%4.0f, %.0f, %.0f)" % (e_now, e_total_offpeak, e_total_peak))

            if write_primary_values_to_file:
                # now write the json file with primary values
                with open(data_p1_file_path, 'w') as fdata_p1:
                    data_p1_json_text = json.dumps(data_p1, sort_keys=True)
                    fdata_p1.write(data_p1_json_text)

            # now write the json file
            with open(data_now_file_path, 'w') as fData:
                p1_data_json_text = json.dumps(data, sort_keys=True)
                fData.write(p1_data_json_text)
        else:
            logger.info('Stopping the loop')

    logger.info('SmartmeterEasy stopped successfully. Have a nice day!')


if __name__ == '__main__':
    main()
