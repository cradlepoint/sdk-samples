import requests
import tarfile
import os


def download_and_extract_tar_gz(url, target_folder):
    try:
        # Create the target folder if it doesn't exist
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)

        # Download the tar.gz file
        print(f"Downloading {url}...")
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to download the file from {url}. Status code: {response.status_code}")
            return

        # Save the file in the target folder
        filename = os.path.join(target_folder, list(filter(None, url.split("/")))[-1])
        with open(filename, "wb") as file:
            file.write(response.content)
        
        # Extract the contents of the tar.gz file
        with tarfile.open(filename, "r:gz") as tar:
            tar.extractall(target_folder)

        # Delete the tar.gz file after extraction
        os.remove(filename)

        print(f"Extracting {filename} completed successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")


def move_file(source, target):
    try:
        os.rename(source, target)
        print(f"Files moved from {source} to {target} successfully.")
    except Exception as e:
        print(f"An error occurred moving {source} to {target}: {e}")
        

def add_executable_perm(filename):
    try:
        # Add executable permissions to the file
        os.chmod(filename, 0o755)
        
        print(f"Executable permissions for {filename} added successfully.")
    except Exception as e:
        print(f"An error occurred adding permissions for {filename}: {e}")


if __name__ == "__main__":
    dl = {
        'arm': 'rproxy-arm-unknown-linux-musleabihf.tar.gz',
        'amd64': 'rproxy-x86_64-unknown-linux-musl.tar.gz',
        'arm64': 'rproxy-aarch64-unknown-linux-musl.tar.gz'
    }

    for arch in ['arm', 'amd64', 'arm64']:
        download_and_extract_tar_gz(f'https://github.com/cayspekko/buildproxy/releases/download/v0.1.0/{dl[arch]}', './')
        move_file("rproxy", f"rproxy_{arch}")
        add_executable_perm(f'./rproxy_{arch}')
