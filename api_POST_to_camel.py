import sys
import os
import requests
from requests.packages.urllib3 import Retry
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth

file = sys.argv[1]
url_POST = sys.argv[2]

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
def apiPOST(file, url_POST):
    try:
        s = requests.Session()
        r_text = 'Go'
        filename = os.path.basename(file)
        with open(file, 'rb') as f:
            r = requests_retry_session(session=s).post(
                url_POST,
                data = {"mysubmit":r_text},
                files={"file": (filename, f)},
                timeout=30
                )
        if (r.status_code and r.status_code == 200) and (r.text and r.text == r_text):
            return 'Success'
        else:
            return 'error: api response: "{}"'.format(r)

    except Exception as e:
        return 'error: {}'.format(e)#

if __name__ == '__main__':
    resultstr = apiPOST(file, url_POST)
    print (resultstr)
