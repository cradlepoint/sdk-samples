import requests

def download_file(url, session=None, timeout=15):
    local_filename = url.split('/')[-1]
    req = session or requests
    # NOTE the stream=True parameter below
    with req.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): 
                # If you have chunk encoded response uncomment if
                # and set chunk_size parameter to None.
                #if chunk: 
                f.write(chunk)
    return local_filename

if __name__ == "__main__":
    import sys
    url = sys.argv[1]
    print("File downloaded:", download_file(url))
