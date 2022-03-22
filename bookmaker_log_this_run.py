import sys
import os
import json
import time
import imp
import traceback
import requests

#---------------------  LOCAL DECLARATIONS

run_metadata_json = sys.argv[1]
config_json = sys.argv[2]
json_log = sys.argv[3]
credentials_json = sys.argv[4]
which_server = sys.argv[5]
success_str = sys.argv[6]

values_list = []
values_dict = {}

#---------------------  FUNCTIONS

def readJSON(filename):
    try:
        with open(filename) as json_data:
            d = json.load(json_data)
            # logger.debug("reading in json file %s" % filename)
            return d
    except:
        return {}

def addItem(newname, key, dict, blankvalue='unavailable', toplevelkey='', exclusions=[]):
    if toplevelkey:
        if toplevelkey in dict:
            addItem(newname, key, dict[toplevelkey], blankvalue, '', exclusions)
        else:
            values_dict[newname] = blankvalue
    elif key in dict:
        if isinstance(dict[key], list):
            if exclusions:
                for x in exclusions:
                    if x in dict[key]:
                        dict[key].remove(x)
            values_dict[newname] = ', '.join(dict[key])
        else:
            values_dict[newname] = dict[key]
    else:
        values_dict[newname] = blankvalue

def setValuesForLog(run_metadata_json, config_json, json_log):
    # try:
    run_metadata_dict = readJSON(run_metadata_json)
    config_dict = readJSON(config_json)
    json_dict = readJSON(json_log)
    # values_list = []
    values_dict['date'] = time.strftime("%y%m%d-%H%M%S")
    # get bookmaker folder
    if 'project' in config_dict and 'stage' in config_dict:
        values_dict['folder'] = '{}_{}'.format(config_dict['project'], config_dict['stage'])
    else:
        values_dict['folder'] = 'unavailable'
    # add other items from json files, where present
    addItem('status', 'output_ok', json_dict, 'unavailable', 'bookmaker_mailer.rb')
    addItem('submitter_email', 'submitter_email', run_metadata_dict)
    addItem('primary_ISBN', 'productid', config_dict)
    addItem('title', 'title', config_dict)
    addItem('imprint', 'imprint', config_dict)
    addItem('style-set', 'doctemplatetype', config_dict)
    addItem('other_files_received', 'submitted_files', json_dict, '', 'tmparchive_direct.rb', ['bookmakerMetadata.json'])
    addItem('design_template', 'design_template', config_dict, '')

    return values_dict, 'success'
    # except:
    #     return [],[],traceback.format_exc()

def invokeApi(values_dict, credentials_json, which_server, success_str):
    api_creds = readJSON(credentials_json)
    if which_server == 'staging':
        values_dict['staging']=True
        api_creds = api_creds.copy()['staging']
    # run api
    r = requests.post(api_creds['logrun_url'], data = values_dict, auth=(api_creds['basicauth_un'], api_creds['basicauth_p']))
    # return result
    try:
    	if not 'error' in r.json():
            return '{}: {}'.format(success_str, r.json()['response']['result'])
    	else:
    		return str(r.json())
    except ValueError:	# < if reponse is not json
    	return r.status_code, r.reason, r.content, r.headers

def logThisRun(run_metadata_json, config_json, json_log, credentials_json, which_server, success_str):
    result_string = ''
    # get values, headers, for post to sheet
    values_dict, result_string = setValuesForLog(run_metadata_json, config_json, json_log)
    if result_string == 'success':
    #     # re-using result_string var again
        try:
            result_string = invokeApi(values_dict, credentials_json, which_server, success_str)
        except:
            return "err invoking gapps_api: {}".format(traceback.format_exc())
    return result_string

if __name__ == '__main__':
    resultstr = logThisRun(run_metadata_json, config_json, json_log, credentials_json, which_server, success_str)
    print resultstr
