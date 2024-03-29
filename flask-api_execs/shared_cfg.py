import sys
import os
import imp
import re
import json
import platform
import zipfile
from datetime import datetime
import logging
import subprocess
from textwrap import dedent
from socket import gethostname
from getpass import getuser
from shutil import copyfile
import shared_cfg


# Define harcoded relative import paths from other repos
utils_repo = os.path.join(sys.path[0], '..', '..', 'utilities')
sendmail = imp.load_source('sendmail', os.path.join(utils_repo, 'python_utils','sendmail.py'))
local_cfg_json = os.path.join(sys.path[0], 'local_cfg.json')

# # # Define key vars and params from input
inputfile = sys.argv[1]
# the relative order of these passed params is set in flask/instance/config.py
user_name = sys.argv[2]
user_email = sys.argv[3]
if len(sys.argv)>4:
    bkmkr_project = sys.argv[4]
parentdir = os.path.dirname(inputfile)
jobId = os.path.basename(parentdir)
file_ext = os.path.splitext(inputfile)[1]
infile_name = os.path.basename(inputfile)

# Other key definitions
# using specified python binary, otherwise py3 from the calling venv is the default
#    defaulting to whatever in system path, override with local config
pypath = 'python'
# same for ruby
rubypath = 'ruby'   # <- use default installed ruby from PATH, or ...
if os.path.exists(local_cfg_json):
    try:
        with open(local_cfg_json) as json_data:
            d = json.load(json_data)
    except ValueError as e:
        logging.error('error with data from local_cfg.json:\n{}'.format(e))
        d = {}
    except:
        d = {}
    if len(d) > 0 and 'python_path' in d and d['python_path'] != '':
        pypath = os.path.normpath(d['python_path'])
    if len(d) > 0 and 'ruby_path' in d and d['ruby_path'] != '':
        rubypath = os.path.normpath(d['ruby_path'])
# # ... use specified ruby binary from hardcoded path \/
# rubypath = os.path.join('C:', os.sep, 'Ruby200', 'bin', 'ruby.exe')
this_script = os.path.basename(sys.argv[0])
runtype_string = 'direct'
server = gethostname()
currentuser = getuser()
alert_emails_to = ['workflows@macmillan.com']
staging_filename = 'staging.txt'
staging_file = os.path.join("C:", os.sep, staging_filename)
logdir_base = os.path.join("S:", os.sep, 'flask-api')    #<< drive
bkmkr_scripts_dir = os.path.join("S:", os.sep, 'resources', 'bookmaker_scripts')
# edits to above ^ for Mac OS / UNIX
if platform.system() != 'Windows':  # for testing:
    pypath = os.path.join(os.sep, 'usr', 'bin', 'python') # <- python 2.7 (system)
    rubypath = 'ruby'
    staging_file = os.path.join(os.sep,"Users", currentuser, staging_filename)
    logdir_base = os.path.join(os.sep, 'Users', currentuser, 'testup')
    bkmkr_scripts_dir = os.path.join(os.sep,'Users', currentuser, 'bookmaker-dev')
# conditional dependent paths
logdir = os.path.join(logdir_base, 'api-exec_logs')
# \/ probably don't need to implement process_watch.py for this app; since it already sends alerts on error
#process_watch_py = os.path.join(bkmkr_scripts_dir, "sectionstart_converter", "xml_docx_stylechecks", "shared_utils", "process_watch.py")
# if os.path.exists(staging_file):  # < this is also not necessary since we are not collecting logs in one place (dropbox)
#     logdir = '{}_stg'.format(logdir)
logfile = os.path.join(logdir, "{}-{}.log".format(this_script.replace('.','_'), datetime.now().strftime("%y-%m")))

# # # ERROR ALERTS info:
err_subject = "ALERT: {}: unexpected error ({})".format(this_script, server)
err_txt  = dedent("""
    Hello honored workflows personnel,

    An unexpected error was encountered while running {this_script}.
    - server/host: {server}
    - logfile: {logfile}
    - errstring: {errstring}
    """)
err_dict = {
    "err_subject": err_subject,
    "err_txt": err_txt,
    "alert_emails_to": alert_emails_to,
    "server": server,
    "logfile": logfile,
    "this_script": this_script
}

# # # EMAIL TEMPLATE for exec file alerts:
alertmail_subject = "{productname} update: a problem with your submitted files"
alertmail_txt = dedent("""
    Hello {uname},

    {productname_cap} encountered the problem(s) listed below when attempting to process your submitted file(s):
    (submitted file(s): {infile_basename})

    {alerttxts}

    Please resolve the above issues and resubmit to {productname}!

    Or contact the workflows team at {to_mail} for further assistance:)
    """)
if os.path.isfile(staging_file):
    alertmail_subject += '- {}'.format(server)
    alertmail_txt += '\n\nSENT FROM BOOKMAKER STAGING (TESTING) SERVER'

# # # FUNCTIONS
def sendExceptionAlert(errstring, err_dict):
    try:
        logging.info("err occurred, attempting send ")
        err_body = err_txt.format(server=err_dict['server'], logfile=err_dict['logfile'], this_script=err_dict['this_script'], errstring=errstring)
        sendmail.sendMail(err_dict['alert_emails_to'], err_dict['err_subject'], err_body)
    except Exception as e:
        logging.error('Error sending Exception alert-mail', exc_info=True)

def try_create_dir(newpath, err_dict):
    try:
        logging.debug("creating dir: {}".format(newpath))
        if not os.path.exists(newpath):
            os.makedirs(newpath)
    except Exception as e:
        logging.error('Destination dir "{}" could not be created'.format(newpath), exc_info=True)
        sendExceptionAlert(e, err_dict)

# handle unzipping as needed
def unzipZips(inputfile, err_dict):
    if os.path.splitext(inputfile)[1] == '.zip':
        logging.debug("zip file, unzipping")
        parentdir = os.path.dirname(inputfile)
        try:
            zf = zipfile.ZipFile(inputfile, 'a')
            zf.extractall(parentdir)
            zf.close()
        except Exception as e:
            logging.error('Error unzipping "{}"'.format(inputfile), exc_info=True)
            sendExceptionAlert(e, err_dict)

def sanitizeFilename(fname, err_dict):
    try:
        basename, file_ext = os.path.splitext(fname)
        sanitized_basename = re.sub(r'[^\w-]','',basename)
        sanitized_fname = sanitized_basename + file_ext
        if fname != sanitized_fname:
            logging.info("sanitized filename, from {} to {}".format(fname, sanitized_fname))
        return sanitized_fname
    except:
        logging.error('Error sanitizing filename "{}"'.format(fname), exc_info=True)
        sendExceptionAlert(e, err_dict)
        return fname

def copyFile(src, dst, err_dict):
    try:
        copyfile(src, dst)
    except:
        logging.error('Error copying file "{}" to "{}"'.format(src, dst), exc_info=True)
        sendExceptionAlert(e, err_dict)
        return fname

# kickoff process via subprocess.popen
def invokeSubprocess(popen_params, product_name, err_dict):
    p = ''
    try:
        logging.debug("popen params for 'invokeSubprocess-{}': \n{}".format(product_name, popen_params))
        p = subprocess.Popen(popen_params)
        logging.info("{} subprocess initiated, pid {}".format(product_name, p.pid))
        # logging.debug("popen output: {}".format(p)) < I don' think this works, b/c we are not piping stdout or anything
        return True
    except Exception as e:
        logging.error("error invoking bkmkr subprocess; params: {}".format(popen_params), exc_info=True)
        if p:
            logging.info("(popen output: {})".format(p))
        sendExceptionAlert(e, err_dict)
        return False
