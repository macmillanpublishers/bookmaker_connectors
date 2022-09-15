import sys
import os
import requests
from requests.auth import HTTPBasicAuth

# send POST request with file
def apiPOST(file, url_POST, uname, pw, params):
    try:
        filename = os.path.basename(file)
        with open(file, 'rb') as f:
            r = requests.post(url_POST,
            params=params,
            auth=HTTPBasicAuth(uname, pw),
            files={'file': (filename, f)})
        if (r.status_code and r.status_code == 200):
            return 'Success'
        else:
            return 'error: api response: "{}"'.format(r.text)

    except Exception as e:
        return 'error: {}'.format(e)#

if __name__ == '__main__':
    # accepting x number of optional parameter k:v pairs from the command line, like so:
    #   python filepath/filename host_url key1 value1 key2 value2 ...
    # if basic auth is not enabled on host you can use dummy values for user and pass, they are ignored
    file = sys.argv[1]
    url_POST = sys.argv[2]
    uname = sys.argv[3]
    pw = sys.argv[4]
    params = {}
    if len(sys.argv) > 5:
        for i in list(range(5, len(sys.argv)-1)):
            if(i%2 == 1):   # if param # is odd it's a param key
                params[sys.argv[i]]=sys.argv[i+1]

    resultstr = apiPOST(file, url_POST, uname, pw, params)
    print (resultstr)
