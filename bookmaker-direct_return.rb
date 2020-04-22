require 'fileutils'
require 'net/http'
require 'httparty'

require_relative '../bookmaker/core/header.rb'
require_relative '../bookmaker/core/metadata.rb'

# ---------------------- VARIABLES

local_log_hash, @log_hash = Bkmkr::Paths.setLocalLoghash

final_dir = Metadata.final_dir
scripts_dir = Bkmkr::Paths.scripts_dir
rsuite_server_json = File.join(Bkmkr::Paths.scripts_dir, "bookmaker_authkeys", "rsuite_servers.json")
zip_wrapper_py = File.join(scripts_dir, "bookmaker_connectors", "zip_wrapper.py")
api_POST_to_RS_py = File.join(scripts_dir, "bookmaker_connectors", "api_POST_to_RS.py")
sendfiles_regexp = File.join(final_dir, "*{_ERROR.txt,_POD.pdf,.epub}")


# ---------------------- METHODS

def readJson(jsonfile, logkey='')
  data_hash = Mcmlln::Tools.readjson(jsonfile)
  return data_hash
rescue => logstring
  return {}
ensure
  Mcmlln::Tools.logtoJson(@log_hash, logkey, logstring)
end

def getFileList(regexp, logkey='')
  filelist = Dir.glob(regexp)
  logstring = filelist
  return filelist
rescue => logstring
ensure
    Mcmlln::Tools.logtoJson(@log_hash, logkey, logstring)
end

def getRsuiteSession(url, auth, logkey='')
  response = HTTParty.get(url, basic_auth: auth)
  return response.code, response.parsed_response['map']['key']
rescue => logstring
ensure
    Mcmlln::Tools.logtoJson(@log_hash, logkey, logstring)
end

def testZipfile(zipfile_fullpath, logkey='')
  zip_test = 'zipfile not present in filesystem'
  if File.file?(zipfile_fullpath)
    zip_test = 'present'
  end
  return zip_test
rescue => logstring
ensure
    Mcmlln::Tools.logtoJson(@log_hash, logkey, logstring)
end

def zipFiles(zip_wrapper_py, target_dir, zipfile_fullpath, files_to_send_list, logkey='')
  zip_test = 'n-a'
  files_to_send_str = files_to_send_list.join('" "')
  arg_string = "\"#{target_dir}\" \"#{zipfile_fullpath}\" \"#{files_to_send_str}\""
  # zip_result = `python #{zip_wrapper_py} #{arg_string}`.strip()   # <-- for local test / debug
  zip_result = Bkmkr::Tools.runpython(zip_wrapper_py, arg_string).strip()
  if zip_result == 'zipped'
      zip_test = testZipfile(zipfile_fullpath, 'test_zipfile_present')
  else
      logstring = "ERR from python zip_wrapper.py: #{zip_result}"
  end
  return zip_test
rescue => logstring
ensure
    Mcmlln::Tools.logtoJson(@log_hash, logkey, logstring)
end

def postZipToRSuite(py_script, url, zipfile_fullpath, logkey='')
  arg_string = "\"#{zipfile_fullpath}\" \"#{url}\""
  # results = `python #{py_script} #{arg_string}`   # <-- for local test / debug
  results = Bkmkr::Tools.runpython(py_script, arg_string).strip()
  result_code, result_msg = results.split('_', 2)
  return result_code, result_msg
rescue => logstring
ensure
    Mcmlln::Tools.logtoJson(@log_hash, logkey, logstring)
end


# # ---------------------- MAIN

# local definitions from json files
api_metadata_hash = readJson(Bkmkr::Paths.api_Metadata_json, 'read_api_metadata_json')
rsuite_isbn = api_metadata_hash['edition_eanisbn13']
if Bkmkr::Project.runtype == 'rsuite'
  rs_server_hash = readJson(rsuite_server_json, 'read_rs_server_json')
  rs_server = api_metadata_hash['rsuite_server']
  serveraddress = rs_server_hash[rs_server]['fqdn']
  api_uname = rs_server_hash[rs_server]['api_uname']
  api_pword = rs_server_hash[rs_server]['api_pword']
  # log key values
  @log_hash['rsuite_isbn'] = rsuite_isbn
  @log_hash['serveraddress'] = serveraddress
end

# get list of files to send from final_dir
files_to_send_list = getFileList(sendfiles_regexp, "files_to_copy")

# # prepare GET & capture rsuite session key
# auth = {username: api_uname, password: api_pword}
# url_GET = "http://#{serveraddress}/rsuite/rest/v2/user/session"
# api_GET_result, sessionkey = getRsuiteSession(url_GET, auth, 'api_GET_rsuite_sessionkey')
#
# # zip files in final_dir (if GET was successful)
# if api_GET_result == 200 && sessionkey
  zipfile_name = "#{rsuite_isbn}.zip"
  zipfile_dir = final_dir
  zipfile_fullpath = File.join(zipfile_dir, zipfile_name)
  @log_hash['expected_zip_path'] = zipfile_fullpath
  zip_test = zipFiles(zip_wrapper_py, zipfile_dir, zipfile_fullpath, files_to_send_list, 'zip_bookmaker_files_to_send')
  @log_hash['zip_test'] = zip_test

#   # if zip was successful, POST zipfile to RSuite!
#   if zip_test == 'present'
#     url_POST = "http://#{serveraddress}/rsuite/rest/v1/api/mpg:webservice.BookmakerUploader?skey=#{sessionkey}"
#     result_code, result_msg  = postZipToRSuite(api_POST_to_RS_py, url_POST, zipfile_fullpath, 'api_POST_zipfile_to_rsuite')
#     # log results, eventually send mail on fail
#     if result_code == '200'
#       logstring = "success: #{result_msg}"
#     else
#       logstring = "ERROR, code: #{result_code}, msg: #{result_msg}"
#     end
#   else
#     logstring = "ERROR: Bookmaker zipfile for upload-to-rsuite not found: \"#{zipfile_fullpath}\""
#   end
# else
#   logstring = "ERROR: Could not get RS sessionkey for user \"#{api_uname}\", upload to RSuite failed"
# end
puts "api_POST_result: ", logstring  #< debug
@log_hash['api_POST_result'] = logstring

# # # Write json log:
Mcmlln::Tools.logtoJson(@log_hash, 'completed', Time.now)
Mcmlln::Tools.write_json(local_log_hash, Bkmkr::Paths.json_log)
