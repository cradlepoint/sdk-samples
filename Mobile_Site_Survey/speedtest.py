#!/usr/bin/env python3
"""
Speedtest module - Reverse compatibility wrapper for Ookla speedtest binary
Provides compatibility with the original speedtest library interface

USAGE:
    # Method 1: Using the module singleton (recommended)
    import speedtest
    speedtest.start()     # Runs the test and returns results
    print(f"Download: {speedtest.results.download} bps")
    print(f"Upload: {speedtest.results.upload} bps")

    # Method 2: Using the class directly (fully compatible with original library)
    from speedtest import Speedtest
    st = Speedtest()
    st.get_best_server()  # Compatibility method (does nothing)
    st.download()         # Runs the full speedtest (download + upload)
    st.upload()           # Compatibility method (does nothing after download)
    print(f"Download: {st.results.download} bps")
    print(f"Upload: {st.results.upload} bps")

    # Method 3: With source address binding
    from speedtest import Speedtest
    st = Speedtest(source_address="192.168.1.100")
    st.download()         # Runs the test
    print(f"Ping: {st.results.ping} ms")
    

NOTES:
    - The Ookla binary runs the entire test (download + upload + server selection) in one command
    - Results are in bits per second (bps) for download/upload, milliseconds (ms) for ping
    - The binary is automatically downloaded if not present
    - download() runs the full test, upload() does nothing (for compatibility)
    - Use download() or start() to actually execute the speedtest
"""

import subprocess
import json
import os
import requests
import tarfile
from datetime import datetime


def download_speedtest_binary():
    """Download and extract the Ookla Speedtest CLI binary"""
    try:
        # Default URL for Ookla Speedtest CLI
        url = "https://install.speedtest.net/app/cli/ookla-speedtest-1.2.0-linux-aarch64.tgz"
        
        # If file doesn't exist, download it
        filename = url.split("/")[-1]
        if not os.path.exists('speedtest'):
            print(f"Downloading {url}...")
            response = requests.get(url)
            if response.status_code != 200:
                raise Exception(f"Failed to download the file from {url}. Status code: {response.status_code}")

            # Save the file
            with open(filename, "wb") as file:
                file.write(response.content)
            
            print(f"Downloaded {filename}")
            
            # Extract the binary from the tar.gz file
            print(f"Extracting {filename}...")
            with tarfile.open(filename, 'r:gz') as tar:
                # Extract the speedtest binary
                for member in tar.getmembers():
                    if member.name.endswith('speedtest') and member.isfile():
                        member.name = 'speedtest'  # Extract as 'speedtest' in current directory
                        tar.extract(member)
                        # Make the file executable
                        os.chmod('speedtest', 0o755)
                        print(f"Extracted and made speedtest executable")
                        break
                else:
                    raise Exception("speedtest binary not found in archive")
            
            # Clean up the tar.gz file
            os.remove(filename)
            print(f"Cleaned up {filename}")
        else:
            print(f"speedtest binary already exists")
        return True
    except Exception as e:
        print(f"An error occurred downloading speedtest: {e}")
        return False


class SpeedtestResults:
    """Class for holding the results of a speedtest"""
    
    def __init__(self, download=0, upload=0, ping=0, server=None, client=None, opener=None, secure=False, bytes_received=0, bytes_sent=0):
        self.download = download  # in bits per second
        self.upload = upload      # in bits per second  
        self.ping = ping          # in milliseconds
        self.server = server or {}
        self.client = client or {}
        self.timestamp = f'{datetime.utcnow().isoformat()}Z'
        self.bytes_received = bytes_received
        self.bytes_sent = bytes_sent
        self._share = None
        self._opener = opener
        
    def share(self):
        """Return the share URL for the speedtest results"""
        return self._share


class Speedtest:
    """Class for performing speedtest operations using the binary speedtest executable"""
    
    def __init__(self, config=None, source_address=None, timeout=60, secure=False, shutdown_event=None):
        self.config = config or {}
        self._source_address = source_address
        self._timeout = timeout
        self._secure = secure
        self._shutdown_event = shutdown_event
        self.results = None
        self.closest = []
        
    def get_best_server(self, servers=None):
        """Get the best server (compatibility method - actual selection happens during test)"""
        # The binary speedtest handles server selection automatically
        # This method exists for compatibility but doesn't need to do anything
        pass
        
    def download(self, callback=None, threads=None):
        """Test download speed - runs the full speedtest"""
        # The binary speedtest runs both download and upload together
        return self.start()
        
    def upload(self, callback=None, pre_allocate=True, threads=None):
        """Test upload speed - compatibility method (does nothing after download)"""
        # Upload is already included in the download() test
        pass
        
    def start(self):
        """Run the actual speedtest using the binary executable"""
        try:
            # Check if speedtest binary exists, if not try to download it
            if not os.path.exists('speedtest'):
                print("Speedtest binary not found, attempting to download...")
                if not download_speedtest_binary():
                    raise FileNotFoundError("Failed to download speedtest binary")
            
            # Build speedtest command
            cmd = ['./speedtest', '--accept-license', '-f', 'json']
            
            # Add source address if specified
            if self._source_address:
                cmd.extend(['-i', self._source_address])
                
            # Run the speedtest
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self._timeout)
            
            if result.returncode != 0:
                raise Exception(f"Speedtest failed with return code {result.returncode}: {result.stderr}")
                
            # Parse JSON output
            data = json.loads(result.stdout)
            
            # Create results object
            # Convert bytes per second to bits per second (multiply by 8)
            download_bps = data.get('download', {}).get('bandwidth', 0) * 8
            upload_bps = data.get('upload', {}).get('bandwidth', 0) * 8
            
            # Extract bytes information from the JSON response
            bytes_received = data.get('download', {}).get('bytes', 0)
            bytes_sent = data.get('upload', {}).get('bytes', 0)
            ping = data.get('ping', {}).get('latency', 0)
            server = data.get('server', {})
            client = data.get('client', {})
            share_url = data.get('result', {}).get('url', '')
            
            self.results = SpeedtestResults(
                download=download_bps,
                upload=upload_bps, 
                ping=ping,
                server=server,
                client=client,
                bytes_received=bytes_received,
                bytes_sent=bytes_sent
            )
            
            # Set the share URL
            self.results._share = share_url
            
            return self.results
            
        except FileNotFoundError:
            raise Exception("Speedtest binary not found and download failed")
        except subprocess.TimeoutExpired:
            raise Exception("Speedtest timed out")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse speedtest output: {e}")
        except Exception as e:
            raise Exception(f"Speedtest failed: {e}")


# Module-level singleton for import speedtest; speedtest.start() pattern
_singleton_instance = None
_singleton_results = None


def start():
    """Start a speedtest using the module singleton"""
    global _singleton_instance, _singleton_results
    
    if _singleton_instance is None:
        _singleton_instance = Speedtest()
    
    _singleton_results = _singleton_instance.start()
    return _singleton_results


def get_results():
    """Get the results from the last speedtest"""
    global _singleton_results
    return _singleton_results


# Make results available at module level for compatibility
@property
def results():
    """Get results from singleton instance"""
    global _singleton_results
    return _singleton_results


# Add results property to module
import sys
sys.modules[__name__].results = results
