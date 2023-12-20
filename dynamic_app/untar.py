import tarfile

def extract(filename, destination):
    with tarfile.open(filename) as gz:
        gz.extractall(destination)

if __name__ == "__main__":
    import sys
    filename, destination = sys.argv[1:]
    extract(filename, destination)