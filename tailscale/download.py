import requests
import tarfile
import os
import shutil

TSVERSION = "1.80.2"

def download(url, target_folder):
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
        return filename
    except Exception as e:
        print(f"An error occurred: {e}")

def extract_tar_gz(filename, target_folder):
    try:
        # Create the target folder if it doesn't exist
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
       
        # Extract the contents of the tar.gz file
        with tarfile.open(filename, "r:gz") as tar:
            tar.extractall(target_folder)

        print(f"Extracting {filename} completed successfully.")
        return filename
    except Exception as e:
        print(f"An error occurred: {e}")

def download_and_extract_tar_gz(url, target_folder):
    filename = download(url, target_folder) # expects a tar.gz file
    filename = extract_tar_gz(filename, target_folder)
    # Delete the tar.gz file after extraction
    os.remove(filename)

def move_files(source_folder, target_folder):
    try:
        # Create the target folder if it doesn't exist
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)

        # Move the files from the source folder to the target folder
        for file in os.listdir(source_folder):
            os.rename(os.path.join(source_folder, file), os.path.join(target_folder, file))
        
        print("Files moved successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")

def rename_file(source, target):
    try:
        os.rename(source, target)
        print(f"Files renamed from {source} to {target} successfully.")
    except Exception as e:
        print(f"An error occurred renaming {source} to {target}: {e}")

def add_executable_perm(filename):
    try:
        # Add executable permissions to the file
        os.chmod(filename, 0o755)
        
        print(f"Executable permissions for {filename} added successfully.")
    except Exception as e:
        print(f"An error occurred adding permissions for {filename}: {e}")

def check_version(version):
    # check version.txt file, if it is missing or the version doesn't match, return false
    try:
        with open('version.txt', 'r') as file:
            if file.read() != version:
                return False
    except FileNotFoundError:
        return False
    return True

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('archs', nargs='*')
    parser.add_argument("-v", "--version", help="Tailscale version", default=TSVERSION)
    args = parser.parse_args()
    if not args.archs:
        archs = (
            'arm', 
            'arm64', 
            # 'amd64',
            # 'mipsle'
            )
    else:
        archs = args.archs
    tsversion = args.version

    if not check_version(tsversion):

        for arch in archs:
            download_and_extract_tar_gz(f'https://pkgs.tailscale.com/stable/tailscale_{tsversion}_{arch}.tgz', './')
            move_files(f'./tailscale_{tsversion}_{arch}/', './')
            shutil.rmtree(f'./tailscale_{tsversion}_{arch}')
            shutil.rmtree('./systemd')
            rename_file('./tailscale', f'./tailscale_{arch}')
            rename_file('./tailscaled', f'./tailscaled_{arch}')
            add_executable_perm(f'./tailscale_{arch}')
            add_executable_perm(f'./tailscaled_{arch}')

        with open('version.txt', 'w') as file:
            file.write(tsversion)

if __name__ == "__main__":
    main()