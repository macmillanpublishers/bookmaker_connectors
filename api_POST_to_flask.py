import sys
import os
import requests

# acceptin optional parameter k:v pairs from the command line, like so:
#   python filepath/filename host_url key1 value1 key2 value2 ...
file = sys.argv[1]
url_POST = sys.argv[2]
params = {}
if len(sys.argv) > 3:
    for i in list(range(3, len(sys.argv)-1)):
        if(i%2 == 1):   # if param # is odd it's a param key
            params[sys.argv[i]]=sys.argv[i+1]

# send POST request with file
def apiPOST(file, url_POST):
    try:
        filename = os.path.basename(file)
        fileobj = open(file,'rb')
        r = requests.post(url_POST, params=params, files={"file": (filename, fileobj)})
        if (r.status_code and r.status_code == 200):
            return 'Success'
        else:
            return 'error: api response: "{}"'.format(r)

    except Exception as e:
        return 'error: {}'.format(e)#

if __name__ == '__main__':
    resultstr = apiPOST(file, url_POST)
    print resultstr
