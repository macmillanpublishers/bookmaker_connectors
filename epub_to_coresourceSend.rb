require 'fileutils'

require_relative '../bookmaker/core/header.rb'
require_relative '../bookmaker/core/metadata.rb'

# ---------------------- VARIABLES

local_log_hash, @log_hash = Bkmkr::Paths.setLocalLoghash

csdir = File.join(Bkmkr::Project.working_dir, "send_to_coresource")
epubregexp = File.join(Bkmkr::Paths.done_dir, Metadata.pisbn, "*.epub")
epub_errfile = File.join(Bkmkr::Paths.done_dir, Metadata.pisbn, "EPUBCHECK_ERROR.txt")

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

# skip coresource upload if epubcheck error-file is present
unless File.file?(epub_errfile)
  # copy all epubs from done dir
  # to coresource_send dir,
  # which then triggers the coresource_connector.rb script in /utilities
  filelist = getFileList(epubregexp, "files_to_copy")
  copyFiles(filelist, csdir, "status")
else
  @loghash['copy_to_coresource_send_dir'] = '"EPUBCHECK_ERROR.txt" file found, skipping copy to coresource_send dir'
end

# Write json log:
Mcmlln::Tools.logtoJson(@log_hash, 'completed', Time.now)
Mcmlln::Tools.write_json(local_log_hash, Bkmkr::Paths.json_log)
