import sys
import os
import requests
from requests.packages.urllib3 import Retry
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth

# retry implementation borrowed from: https://www.peterbe.com/plog/best-practice-with-retries-with-requests
def requests_retry_session(
    retries=3,
    backoff_factor=0.5,
    # status_forcelist=(500, 502, 504),
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        # status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# send POST request with file
def apiPOST(file, url_POST, uname, pw, params):
    try:
        s = requests.Session()
        filename = os.path.basename(file)
        with open(file, 'rb') as f:
            r = requests_retry_session(session=s).post(
                url_POST,
                params=params,
                auth=HTTPBasicAuth(uname, pw),
                files={'file': (filename, f)},
                timeout=20
                )
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
