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
post_urls_json = File.join(Bkmkr::Paths.scripts_dir, "bookmaker_authkeys", "camelPOST_urls.json")
zip_wrapper_py = File.join(scripts_dir, "bookmaker_connectors", "zip_wrapper.py")
api_POST_to_camel_py = File.join(scripts_dir, "bookmaker_connectors", "api_POST_to_camel.py")
sendfiles_regexp = File.join(final_dir, "*{_ERROR.txt,_POD.pdf,.epub}")
testing_value_file = File.join(Bkmkr::Paths.resource_dir, "staging.txt")
api_POST_results = ''
post_url_productstring = 'bookmaker'


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

# this function identical to one in validator_cleanup_direct, except added 'bookmaker_project' param
def getPOSTurl(url_productstring, post_urls_hash, testing_value_file, bookmaker_project, relative_destpath)
  # get url
  post_url = post_urls_hash[url_productstring]
  if File.file?(testing_value_file)
    post_url = post_urls_hash["#{url_productstring}_stg"]
  end
  # add bookmaker project name
  post_url += "/#{bookmaker_project.downcase}"
  # add dest_folder
  post_url += "?folder=#{relative_destpath}"
  return post_url
rescue => e
  p e
end

## wrapping Bkmkr::Tools.runpython in a new method for this script; to return a result for json_logfile
def localRunPython(py_script, args, logkey='')
	result = Bkmkr::Tools.runpython(py_script, args).strip()
  logstring = "result_string: #{result}"
  return result
rescue => logstring
ensure
  Mcmlln::Tools.logtoJson(@log_hash, logkey, logstring)
end

# this function identical to one in validator_cleanup_direct; except for .py invocation line
def sendFilesToDrive(files_to_send_list, api_POST_to_camel_py, post_url)
  #loop through files to upload:
  api_result_errs = ''
  for file in files_to_send_list
    argstring = "#{file} #{post_url}"
    api_result = localRunPython(api_POST_to_camel_py, argstring, "api_POST_to_camel--file:_#{file}")
    if api_result.downcase != 'success'
      api_result_errs += "- api_err: \'#{api_result}\', file: \'#{file}\'\n"
    end
  end
  if api_result_errs == ''
    api_POST_results = 'success'
  else
    api_POST_results = api_result_errs
  end
  return api_POST_results
rescue => e
  p e
  return "error with 'sendFilesToDrive': #{e}"
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
post_urls_hash = readJson(post_urls_json, 'read_camel_POSTurls_json')

# get list of files to send from final_dir
files_to_send_list = getFileList(sendfiles_regexp, "files_to_copy")
@log_hash['files_to_send_list'] = files_to_send_list

# different steps by runtype
if Bkmkr::Project.runtype == 'direct'

  # get post URL together
  # set destpath for url: project/tmpdir
  bookmaker_project = File.basename(File.dirname(Bkmkr::Paths.project_tmp_dir))
  this_tmpdir_name = File.basename(Bkmkr::Paths.project_tmp_dir)
  post_url = getPOSTurl(post_url_productstring, post_urls_hash, Val::Paths.testing_value_file, bookmaker_project, this_tmpdir_name)

  # send files
  api_POST_results = sendFilesToDrive(files_to_send_list, api_POST_to_camel_py, post_url)

else
  rsuite_isbn = api_metadata_hash['edition_eanisbn13']
  rs_server_hash = readJson(rsuite_server_json, 'read_rs_server_json')
  rs_server = api_metadata_hash['rsuite_server']
  serveraddress = rs_server_hash[rs_server]['fqdn']
  api_uname = rs_server_hash[rs_server]['api_uname']
  api_pword = rs_server_hash[rs_server]['api_pword']
  # log key values
  @log_hash['rsuite_isbn'] = rsuite_isbn
  @log_hash['serveraddress'] = serveraddress

  # prepare GET & capture rsuite session key
  auth = {username: api_uname, password: api_pword}
  url_GET = "http://#{serveraddress}/rsuite/rest/v2/user/session"
  api_GET_result, sessionkey = getRsuiteSession(url_GET, auth, 'api_GET_rsuite_sessionkey')

  # zip files in final_dir (if GET was successful)
  if api_GET_result == 200 && sessionkey
    zipfile_name = "#{rsuite_isbn}.zip"
    zipfile_dir = final_dir
    zipfile_fullpath = File.join(zipfile_dir, zipfile_name)
    @log_hash['expected_zip_path'] = zipfile_fullpath
    zip_test = zipFiles(zip_wrapper_py, zipfile_dir, zipfile_fullpath, files_to_send_list, 'zip_bookmaker_files_to_send')
    @log_hash['zip_test'] = zip_test

    # if zip was successful, POST zipfile to RSuite!
    if zip_test == 'present'
      url_POST = "http://#{serveraddress}/rsuite/rest/v1/api/mpg:webservice.BookmakerUploader?skey=#{sessionkey}"
      result_code, result_msg  = postZipToRSuite(api_POST_to_RS_py, url_POST, zipfile_fullpath, 'api_POST_zipfile_to_rsuite')
      # log results, eventually send mail on fail
      if result_code == '200'
        api_POST_results = "success: #{result_msg}"
      else
        api_POST_results = "ERROR, code: #{result_code}, msg: #{result_msg}"
      end
    else
      api_POST_results = "ERROR: Bookmaker zipfile for upload-to-rsuite not found: \"#{zipfile_fullpath}\""
    end
  else
    api_POST_results = "ERROR: Could not get RS sessionkey for user \"#{api_uname}\", upload to RSuite failed"
  end
end

puts "api_POST_results: ", api_POST_results  #< debug
@log_hash['api_POST_results'] = api_POST_results

# # # Write json log:
Mcmlln::Tools.logtoJson(@log_hash, 'completed', Time.now)
Mcmlln::Tools.write_json(local_log_hash, Bkmkr::Paths.json_log)
