import sys
import os
import json
import time
import imp
import traceback

#---------------------  LOCAL DECLARATIONS

gworksheet_id = sys.argv[1]
sheetname = sys.argv[2]
run_metadata_json = sys.argv[3]
config_json = sys.argv[4]
json_log = sys.argv[5]
credentials_json = sys.argv[6]

sheets_api_path = os.path.join(sys.path[0],'..','utilities','python_utils','googlesheets_api.py')
sheets_api = imp.load_source('sheets_api', sheets_api_path)

values_list = []
values_dict = {}
result_string = ''

#---------------------  FUNCTIONS

def readJSON(filename):
    try:
        with open(filename) as json_data:
            d = json.load(json_data)
            logger.debug("reading in json file %s" % filename)
            return d
    except:
        return {}

def addItem(newname, key, dict, blankvalue='unavailable', toplevelkey=''):
    if toplevelkey:
        if toplevelkey in dict:
            addItem(newname, key, dict, blankvalue)
        else:
            values_dict[newname] = blankvalue
    elif key in dict:
        if isinstance(dict[key], list):
            values_dict[newname] = ', '.join(dict[key])
        else:
            values_dict[newname] = dict[key]
    else:
        values_dict[newname] = blankvalue

def setValuesForLog(run_metadata_json, config_json, json_log):
    try:
        run_metadata_dict = readJSON(run_metadata_json)
        config_dict = readJSON(config_json)
        json_dict = readJSON(json_log)
        # values_list = []
        values_dict['date'] = time.strftime("%y%m%d-%H%M%S")
        # get bookmaker folder
        if 'project' in config_dict and 'stage' in config_dict:
            values_dict['folder'] = '{}_{}'.format(project, stage)
        else:
            values_dict['folder'] = 'unavailable'
        # add other items from json files, where present
        addItem('status', 'output_ok', json_dict, 'unavailable', 'bookmaker_mailer.rb')
        addItem('submitter_email', 'submitter_email', run_metadata_dict)
        addItem('primary_ISBN', 'productid', config_dict)
        addItem('title', 'title', config_dict)
        addItem('imprint', 'imprint', config_dict)
        addItem('style-set', 'doctemplatetype', config_dict)
        addItem('other_files_received', 'submitted_files', json_dict, '', 'tmparchive_direct.rb')
        addItem('design_template', 'design_template', config_dict, '')

        return values_dict.keys(), list(values_dict.values()), 'success'
    except:
        return [],[],traceback.format_exc()

def updateSheetHeaderRow(credentials_json, gworksheet_id, values_list, sheetname):
    # sheets function is wrapped in a try block, we don't need one here.
    r = sheets_api.updateSheet(credentials_json, gworksheet_id, values_list, '{}!A:A'.format(sheetname))
    if isinstance(r, dict) and 'updatedRows' in r and r['updatedRows'] == 1:
        return 'success'
    else:
        return 'error: api response: "{}"'.format(r)

def logToSheet(credentials_json, gworksheet_id, values_list, sheetname):
    # sheets function is wrapped in a try block, we don't need one here.
    r = sheets_api.appendSheet(credentials_json, gworksheet_id, values_list, sheetname)
    if isinstance(r, dict) and 'updatedRows' in r and r['updatedRows'] == 1:
        return 'success'
    else:
        return 'error: api response: "{}"'.format(r)

def logThisRun(run_metadata_json, config_json, json_log, credentials_json, gworksheet_id, sheetname):
    # get values, headers, for post to sheet
    keys_list, values_list, result_string = setValuesForLog(run_metadata_json, config_json, json_log)
    # update headers for sheet if set_Values function succeeded
    if result_string == 'success':
        # re-using result_string var again
        result_string = updateSheetHeaderRow(credentials_json, gworksheet_id, keys_list, sheetname)
    # post new values to sheet if update headers succeeded
    if result_string == 'success':
        # result_string equaled success to get here, now we re-set it for update-sheets_api call
        result_string = logToSheet(credentials_json, gworksheet_id, values_list, sheetname)
    # this value is output for ruby calling function.
    return result_string
