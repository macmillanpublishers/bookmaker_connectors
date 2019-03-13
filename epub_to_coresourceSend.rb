require 'fileutils'

require_relative '../bookmaker/core/header.rb'
require_relative '../bookmaker/core/metadata.rb'

# ---------------------- VARIABLES

local_log_hash, @log_hash = Bkmkr::Paths.setLocalLoghash

outputdirs_json = File.join(Bkmkr::Paths.scripts_dir, "bookmaker_connectors", "bookmakerbot_outputdirs.json")
epubregexp = File.join(Bkmkr::Paths.done_dir, Metadata.pisbn, "*.epub")
epub_errfile = File.join(Bkmkr::Paths.done_dir, Metadata.pisbn, "EPUBCHECK_ERROR.txt")
testing_value_file = File.join(Bkmkr::Paths.resource_dir, "staging.txt")

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

def copyFiles(files, dest, logkey='')
  FileUtils.cp_r(files, dest)
  logstring = 'copying to send_to_coresource folder'
rescue => logstring
ensure
    Mcmlln::Tools.logtoJson(@log_hash, logkey, logstring)
end

# ---------------------- PROCESSES

config_hash = readJson(Metadata.configfile, 'read_config_json')
outputdir_hash = readJson(outputdirs_json, 'read_outputdirs_json')
#local definition(s) based on config.json/doctemplatetype:
doctemplatetype = config_hash['doctemplatetype']
epub_outputdir = File.join(Bkmkr::Project.working_dir, outputdir_hash[doctemplatetype])
@log_hash['doctemplatetype_found'] = doctemplatetype
@log_hash['epub_outputdir'] = epub_outputdir

# skip coresource upload if we are on staging server or epubcheck error-file is present
if File.file?(testing_value_file)
  @log_hash['status'] = 'on staging server, skipping upload to coresource'
elsif File.file?(epub_errfile)
  @log_hash['status'] = 'EPUBCHECK_ERROR.txt file found, skipping upload to coresource'
else
  # copy all epubs from done dir
  # to coresource_send dir (or other destination based on doc_template type),
  # which then triggers the coresource_connector.rb script in /utilities
  filelist = getFileList(epubregexp, "files_to_copy")
  copyFiles(filelist, epub_outputdir, "status")
end

# Write json log:
Mcmlln::Tools.logtoJson(@log_hash, 'completed', Time.now)
Mcmlln::Tools.write_json(local_log_hash, Bkmkr::Paths.json_log)
