require 'fileutils'

require_relative '../bookmaker/core/header.rb'
require_relative '../bookmaker/core/metadata.rb'

# ---------------------- VARIABLES

local_log_hash, @log_hash = Bkmkr::Paths.setLocalLoghash

csdir = File.join(Bkmkr::Project.working_dir, "send_to_coresource")
epubregexp = File.join(Bkmkr::Paths.done_dir, Metadata.pisbn, "*.epub")

# ---------------------- METHODS

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

# copy all epubs from done dir
# to coresource_send dir,
# which then triggers the coresource_connector.rb script in /utilities
filelist = getFileList(epubregexp, "files_to_copy")
copyFiles(filelist, csdir, "status")

# Write json log:
Mcmlln::Tools.logtoJson(@log_hash, 'completed', Time.now)
Mcmlln::Tools.write_json(local_log_hash, Bkmkr::Paths.json_log)