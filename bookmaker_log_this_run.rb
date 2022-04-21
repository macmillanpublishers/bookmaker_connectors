require 'fileutils'

require_relative '../bookmaker/core/header.rb'
require_relative '../bookmaker/core/metadata.rb'

# ---------------------- VARIABLES

local_log_hash, @log_hash = Bkmkr::Paths.setLocalLoghash

google_creds_json = File.join(Bkmkr::Paths.scripts_dir, "bookmaker_authkeys", "gapps_api_info.json")
json_log = Bkmkr::Paths.json_log
userinfo_json = Bkmkr::Paths.api_Metadata_json
config_json = Metadata.configfile
bm_log_run_py = File.join(Bkmkr::Paths.scripts_dir, "bookmaker_connectors", "bookmaker_log_this_run.py")
testing_value_file = File.join(Bkmkr::Paths.resource_dir, "staging.txt")
api_success_str = 'api_success'
api_results = ''
sendmail_py = File.join(Bkmkr::Paths.scripts_dir, "utilities", "python_utils", "sendmail.py")
workflows_email = 'workflows@macmillan.com'


# ---------------------- METHODS

def whichServer(testing_value_file, logkey='')
  if File.file?(testing_value_file)
    sname = 'staging'
  else
    sname = 'production'
  end
  return sname
rescue => logstring
  puts 'error running "whichServer", defaulting to staging server'
  return 'staging'
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

def writeFile(tmpdir, apierr, whichserver, logkey='')
  file = File.join(tmpdir, 'runlog_errmail.txt')
  bookmaker_run = File.basename(tmpdir)
  if whichserver == 'staging'
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

# get vars based on which server we're on
which_server = whichServer(testing_value_file, 'check_if_prod_or_stg_server')

# run our function!
#   use of \"s in args may not be strictly necessary but is safer with possible spaces in filepaths
sheet_api_args = "\"#{userinfo_json}\" \"#{config_json}\" \"#{json_log}\" \"#{google_creds_json}\" \"#{which_server}\" \"#{api_success_str}\""
api_results = localRunPython(bm_log_run_py, sheet_api_args, "sheets_api-log_run_to_gworksheet")
# puts "api_results: ", api_results  #< debug
@log_hash['api_results'] = api_results.strip

# send mail on api err result
if !(api_results.strip.start_with?(api_success_str) && api_results.strip.include?('entry added'))
  # write the text of the mail to file, for pickup by python mailer.
  message_txtfile = writeFile(Bkmkr::Paths.project_tmp_dir, api_results, which_server, "write_emailtxt_to_file")
  # sendmail
  errmail_args = "\"#{workflows_email}\" \"\" \"#{message_txtfile}\""
  errmail_results = localRunPython(sendmail_py, errmail_args, "invoke_sendmail-py")
  @log_hash['errmail_results'] = errmail_results
end

# # # Write json log:
Mcmlln::Tools.logtoJson(@log_hash, 'completed', Time.now)
Mcmlln::Tools.write_json(local_log_hash, Bkmkr::Paths.json_log)
