import sys
import os
import requests

file = sys.argv[1]
url_POST = sys.argv[2]

# send POST request with file
def apiPOST(file, url_POST):
    try:
        r_text = 'Go'
        filename = os.path.basename(file)
        fileobj = open(file,'rb')
        r = requests.post(url_POST, data = {"mysubmit":r_text}, files={"file": (filename, fileobj)})
        if (r.status_code and r.status_code == 200) and (r.text and r.text == r_text):
            return 'Success'
        else:
            return 'error: api response: "{}"'.format(r)

    except Exception as e:
        return 'error: {}'.format(e)#

if __name__ == '__main__':
    resultstr = apiPOST(file, url_POST)
    print resultstr
