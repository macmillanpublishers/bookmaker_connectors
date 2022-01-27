require 'fileutils'

require_relative '../bookmaker/core/header.rb'
require_relative '../bookmaker/core/metadata.rb'

# ---------------------- VARIABLES

local_log_hash, @log_hash = Bkmkr::Paths.setLocalLoghash

google_creds_json = File.join(Bkmkr::Paths.scripts_dir, "bookmaker_authkeys", "drive-api_oauth2credentials_workflows.json")
google_ids_json = File.join(Bkmkr::Paths.scripts_dir, "bookmaker_authkeys", "drive_object_ids.json")
gworksheet_basename = 'bm_log_worksheet'
json_log = Bkmkr::Paths.json_log
userinfo_json = Bkmkr::Paths.api_Metadata_json
config_json = Metadata.configfile
bm_log_run_py = File.join(Bkmkr::Paths.scripts_dir, "bookmaker_connectors", "bookmaker_log_this_run.py")
testing_value_file = File.join(Bkmkr::Paths.resource_dir, "staging.txt")
stg_string = '_stg'
sheet_api_results = ''
sendmail_py = File.join(Bkmkr::Paths.scripts_dir, "utilities", "python_utils", "sendmail.py")
workflows_email = 'workflows@macmillan.com'


# ---------------------- METHODS

def whichServer(testing_value_file, stg_string, logkey='')
  if File.file?(testing_value_file)
    stg_string = stg_string
  else
    stg_string = ''
  end
  return stg_string
rescue => logstring
  puts 'error running "whichServer", defaulting to staging server'
  return '_stg'
ensure
  Mcmlln::Tools.logtoJson(@log_hash, logkey, logstring)
end

def readJson(jsonfile, logkey='')
  data_hash = Mcmlln::Tools.readjson(jsonfile)
  return data_hash
rescue => logstring
  return {}
ensure
  Mcmlln::Tools.logtoJson(@log_hash, logkey, logstring)
end

## wrapping Bkmkr::Tools.runpython in a new method for this script; to return a result for json_logfile
def localRunPython(py_script, args, logkey='')
	results = Bkmkr::Tools.runpython(py_script, args)
  return results
rescue => logstring
ensure
  Mcmlln::Tools.logtoJson(@log_hash, logkey, logstring)
end

def writeFile(tmpdir, apierr, whichserver, stg_string, logkey='')
  file = File.join(tmpdir, 'runlog_errmail.txt')
  bookmaker_run = File.basename(tmpdir)
  if whichserver == stg_string
    server = "NYAUTOMATION_STG"
  else
    server = "NYAUTOMATION_01"
  end
  message = "Bookmaker-logging error for \"#{bookmaker_run}\"\n\n" #<-- this is the email Subject
  message += "Hello honorable workflows personnel,\n\n"
  message += "An error occurred while trying to log details for bookmaker-run \"#{bookmaker_run}\" to target Google-sheet.\n\n"
  message += "Error message details:\n"
  message += "#{apierr}\n\n"
  message += "Happy troubleshooting!\n\n"
  message += "** This message sent from bookmaker_connectors/bookmaker_log_this_run.rb, on #{server} **"
  File.open(file, "w") do |f|
    f.puts(message)
  end
  return file
rescue => logstring
  return ''
ensure
  Mcmlln::Tools.logtoJson(@log_hash, logkey, logstring)
end

# # ---------------------- MAIN

# local definitions from json files
google_ids_json = readJson(google_ids_json, 'read_google_ids_json')
# get suffix based on which server we're on
stg_suffix = whichServer(testing_value_file, stg_string, 'check_if_prod_or_stg_server')
gworksheet_id = google_ids_json["#{gworksheet_basename}#{stg_suffix}"]["id"]
sheetname = google_ids_json["#{gworksheet_basename}#{stg_suffix}"]["sheetname"]

# run our function!
#   use of \"s in args may not be strictly necessary but is safer with possible spaces in filepaths
sheet_api_args = "\"#{json_log}\" \"#{userinfo_json}\" \"#{config_json}\" \"#{gworksheet_id}\" \"#{google_creds_json}\""
sheet_api_results = localRunPython(bm_log_run_py, sheet_api_args, "sheets_api-log_run_to_gworksheet")
# puts "sheet_api_results: ", sheet_api_results  #< debug
@log_hash['sheet_api_results'] = sheet_api_results

if api_result != 'success'
  # write the text of the mail to file, for pickup by python mailer.
  message_txtfile = writeFile(Bkmkr::Paths.project_tmp_dir, api_result, stg_suffix, stg_string, "write_emailtxt_to_file")
  # sendmail
  errmail_args = "\"#{workflows_email}\" \"\" \"#{message_txtfile}\""
  errmail_results = localRunPython(sendmail_py, errmail_args, "invoke_sendmail-py")
  @log_hash['errmail_results'] = errmail_results
end

# # # Write json log:
Mcmlln::Tools.logtoJson(@log_hash, 'completed', Time.now)
Mcmlln::Tools.write_json(local_log_hash, Bkmkr::Paths.json_log)
