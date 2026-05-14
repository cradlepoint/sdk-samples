"""
Copyright © 2017 Cradlepoint, Inc. <www.cradlepoint.com>.  All rights reserved.
This file contains confidential information of Cradlepoint, Inc. and your
use of this file is subject to the Cradlepoint Software License Agreement
distributed with this file. Unauthorized reproduction or distribution of
this file is subject to civil and criminal penalties.
"""

import os
import time
import subprocess
import cp
import select
import json
from threading import Thread
from datetime import datetime

# Constants
SPEEDTEST_TIMEOUT = 90
OOKLA_ERROR_WITH_IFACE = "Server Selection - Failed to find a working test server. (NoServers)"
WAN_STATUS_BASE_PATH = "/status/wan/devices/"


def log(message):
    """Simple logging function using cp.log"""
    cp.log(message)


class ProcessKillerThread(Thread):
    """A thread to kill a process after a given time limit."""
    def __init__(self, subproc, limit):
        super(ProcessKillerThread, self).__init__()
        self.subproc = subproc
        self.limit = limit
        self.daemon = True

    def run(self):
        start = time.time()
        while (time.time() - start) < self.limit:
            time.sleep(.25)
            if self.subproc.poll() is not None:
                return

        if self.subproc.poll() is None:
            log(f"Killing speed test process {self.subproc.pid}, ran too long: {time.time() - start:.1f}s")
            self.subproc.kill()


class SpeedtestResults:
    """Class for holding the results of a speedtest"""
    
    def __init__(self, download=0, upload=0, ping=0, server=None, client=None, bytes_received=0, bytes_sent=0, isp=None):
        self.download = download  # in bits per second
        self.upload = upload      # in bits per second  
        self.ping = ping          # in milliseconds
        self.server = server or {}
        self.client = client or {}
        self.isp = isp or ''      # Ookla-reported ISP (may be top-level in JSON)
        self.timestamp = f'{datetime.utcnow().isoformat()}Z'
        self.bytes_received = bytes_received
        self.bytes_sent = bytes_sent
        self._share = None


class Speedtest:
    """Class for performing speedtest operations using the Ookla binary executable"""
    
    def __init__(self, config=None, source_address=None, timeout=60, secure=False, shutdown_event=None, interface=None):
        self.config = config or {}
        self._source_address = source_address
        self._interface = interface
        self._timeout = timeout
        self._secure = secure
        self._shutdown_event = shutdown_event
        self.results = None
        self.closest = []
        # Use trial config URL to get fresh license each time (avoids expired settings.json license errors)
        self._config_url = "https://www.speedtest.net/api/embed/trial/config"
        
    def get_best_server(self, servers=None):
        """Get the best server (compatibility method - actual selection happens during test)"""
        # The Ookla binary handles server selection automatically
        # This method exists for compatibility but doesn't need to do anything
        pass
        
    def download(self, callback=None, threads=None):
        """Test download speed - runs full test but only returns download results"""
        # Ookla binary doesn't support --no-upload flag, so we run full test
        return self.start(test_type='download')
        
    def upload(self, callback=None, pre_allocate=True, threads=None):
        """Test upload speed - runs full test but only returns upload results"""
        # Ookla binary doesn't support --no-download flag, so we run full test
        return self.start(test_type='upload')
    
    def download_and_upload(self, callback=None, threads=None):
        """Test both download and upload (default behavior)"""
        return self.start(test_type='both')
    
    def _get_interface_info(self):
        """Get interface information for routing, including connection state"""
        try:
            # If source_address is provided, find the interface for it
            if self._source_address:
                wan_devices = cp.get(WAN_STATUS_BASE_PATH)
                if wan_devices and isinstance(wan_devices, dict):
                    for key, value in wan_devices.items():
                        if isinstance(value, dict):
                            ipinfo = value.get('status', {}).get('ipinfo', {})
                            if ipinfo.get('ip_address') == self._source_address:
                                iface = value.get('info', {}).get('iface')
                                gateway = ipinfo.get('gateway')
                                connection_state = value.get('status', {}).get('connection_state')
                                return iface, gateway, self._source_address, connection_state
            
            # If interface name is provided
            if self._interface:
                wan_devices = cp.get(WAN_STATUS_BASE_PATH)
                if wan_devices and isinstance(wan_devices, dict):
                    for key, value in wan_devices.items():
                        if isinstance(value, dict) and value.get('info', {}).get('iface') == self._interface:
                            ipinfo = value.get('status', {}).get('ipinfo', {})
                            gateway = ipinfo.get('gateway')
                            ip_address = ipinfo.get('ip_address')
                            connection_state = value.get('status', {}).get('connection_state')
                            return self._interface, gateway, ip_address, connection_state
            
            return None, None, None, None
        except Exception as e:
            log(f"Error getting interface info: {e}")
            return None, None, None, None
    
    def _monitor_speedtest_output(self, process):
        """Monitor speedtest process output in real-time and return immediately on result or error"""
        parsed_data = None
        fatal_error = False
        error_messages = []  # Collect all error messages for detailed logging
        all_output_lines = []  # Collect all output for debugging
        
        # Use select with timeout to check if stdout is ready
        try:
            read_ready, _, _ = select.select([process.stdout], [], [], 30)
            if not read_ready:
                log("Unable to read from stdout of speedtest process.")
                fatal_error = True
                return None, fatal_error
        except Exception as e:
            log(f"Error in select: {e}")
            fatal_error = True
            return None, fatal_error
        
        # Check if process has already ended before we start reading
        # Even if process failed, try to read output for partial results
        if process.returncode is not None:
            # Try to read any remaining output (even if process failed)
            for line in process.stdout:
                line_str = str(line).strip()
                if not line_str:
                    continue
                all_output_lines.append(line_str)
                try:
                    line_json = json.loads(line_str)
                    if line_json.get("type") == "result":
                        parsed_data = line_json
                        if process.returncode == 0:
                            log("Speed test process completed successfully")
                        else:
                            log(f"Speed test process exited with return code {process.returncode}, but result data available")
                        # Return data even if process failed - may have partial results
                        return parsed_data, False
                    # Capture error messages even from failed process
                    if line_json.get("type") == "log" and line_json.get("level") in ["error", "warning"]:
                        error_messages.append(line_json.get("message", ""))
                    if "error" in line_json:
                        error_messages.append(str(line_json.get("error", "")))
                except json.JSONDecodeError:
                    # Non-JSON line - might be an error message
                    if line_str and (line_str.lower().find("error") >= 0 or line_str.lower().find("fail") >= 0 or 
                                     line_str.lower().find("socket") >= 0 or line_str.lower().find("cannot") >= 0):
                        error_messages.append(line_str)
            # No result data found - only treat as fatal if we couldn't get any data
            if process.returncode != 0:
                error_details = f"Speed test process failed with return code {process.returncode}"
                if error_messages:
                    error_details += f". Error messages: {'; '.join(error_messages[:5])}"  # Limit to first 5 errors
                if all_output_lines:
                    error_details += f". Last output lines: {'; '.join(all_output_lines[-3:])}"  # Last 3 lines
                log(error_details)
                fatal_error = True
                return None, fatal_error
            return None, False
        
        # Read output line by line (process is still running)
        for line in process.stdout:
            line_str = str(line).strip()
            if not line_str:
                continue
            
            all_output_lines.append(line_str)
            
            # Check for TimeoutException or network errors (before JSON parsing)
            # But don't break immediately - continue reading to see if we get a result message with partial data
            if "TimeoutException" in line_str or "Network is unreachable" in line_str:
                log(f"Speedtest error detected: {line_str}")
                error_messages.append(line_str)
                # Don't set fatal_error yet - continue reading to check for partial results
                # fatal_error will be set later if we don't get a result message
            
            # Check for socket errors and other common errors in raw output
            socket_errors = ["socket", "Cannot open socket", "Connection refused", "Connection reset", 
                           "Network unreachable", "No route to host", "Permission denied"]
            for err in socket_errors:
                if err.lower() in line_str.lower():
                    log(f"Speedtest network/socket error detected: {line_str}")
                    error_messages.append(line_str)
            
            # Attempt to parse JSON from the line
            try:
                line_json = json.loads(line_str)
            except json.JSONDecodeError:
                # Non-JSON line - might be an error message, log if it looks like an error
                if line_str and (line_str.lower().find("error") >= 0 or line_str.lower().find("fail") >= 0 or 
                                 line_str.lower().find("socket") >= 0 or line_str.lower().find("cannot") >= 0):
                    log(f"Speedtest non-JSON error output: {line_str}")
                    error_messages.append(line_str)
                continue
            
            # Handle specific message types
            message_type = line_json.get("type")
            
            # Skip logging progress messages (download/upload progress)
            if message_type in ["download", "upload"]:
                # These are progress updates - don't log them to reduce spam
                continue
            
            # Log important messages (errors, results, log messages, ping, etc.)
            if message_type == "result":
                log("Speedtest result received")
                parsed_data = line_json
                # Got result - can return immediately
                break
            
            elif message_type == "log":
                message = line_json.get("message", "")
                level = line_json.get("level", "info")
                # Log ALL error and warning level messages with full details
                if level in ["error", "warning"]:
                    log(f"Speedtest {level}: {message}")
                    error_messages.append(message)
                # Log info level messages that contain errors
                elif level == "info" and ("error" in message.lower() or "fail" in message.lower() or 
                                          "socket" in message.lower() or "cannot" in message.lower()):
                    log(f"Speedtest info (error-related): {message}")
                    error_messages.append(message)
                # Check for configuration errors that should be treated as fatal
                if OOKLA_ERROR_WITH_IFACE in str(message):
                    fatal_error = True
                    break
                # Configuration errors are fatal - can't proceed without config
                if "ConfigurationError" in str(message) or "Could not retrieve or read configuration" in str(message):
                    log(f"Speedtest configuration error: {message}")
                    fatal_error = True
                    break
            
            elif message_type == "ping":
                # Log ping start but not every ping update
                ping_data = line_json.get("ping", {})
                if ping_data.get("progress", 0) == 0:
                    log("Speedtest ping started")
            
            elif "error" in line_json:
                # Check for general errors in the parsed JSON
                error_message = line_json["error"]
                log(f"Error encountered: {error_message}")
                error_messages.append(str(error_message))
                # Don't break immediately - continue reading to check for partial results
                # Only set fatal_error if we don't get a result message
            
            else:
                # Handle other message types - log if there's an error
                if "error" in str(line_json) or "Error" in str(line_json):
                    log(f"Error found in {message_type} message: {line_json}")
                    error_messages.append(str(line_json))
                    # Don't set fatal_error - continue reading to check for partial results
        
        # If we got a result message, don't treat as fatal even if there were errors
        if parsed_data:
            if error_messages:
                log(f"Speedtest completed with result but had {len(error_messages)} error(s): {'; '.join(error_messages[:3])}")
            return parsed_data, False
        
        # Only treat as fatal if we got no result data at all
        if error_messages:
            log(f"Speedtest failed with {len(error_messages)} error message(s): {'; '.join(error_messages[:5])}")
        return parsed_data, fatal_error
    
    def _run_speedtest_with_mode(self, mode, iface, gateway, iface_ip, connection_state, test_type='both'):
        """Run speedtest with a specific mode (iface or iface_ip)
        test_type: 'download', 'upload', or 'both' (default)"""
        # No routing setup needed - source_route() handles route tables and policies
        # The route policy will route all traffic from source_ip through the modem interface
        
        # Build speedtest command - use JSONL for streaming output
        # Always use -c flag with trial config URL to get fresh license (avoids expired settings.json)
        # Note: Ookla binary doesn't support --no-upload or --no-download flags
        # We always run the full test and filter results based on test_type
        cmd = ['./ookla', '-f', 'jsonl', '-c', self._config_url]
        
        # Handle standby interfaces - use routing only, no binding
        if connection_state == "standby":
            # For standby interfaces, don't bind to interface
            # Routes will handle traffic direction
            log("Interface is in standby mode - using routing only")
        elif mode == "iface" and iface and not self._source_address:
            # Use interface name binding
            cmd.extend(['-I', iface])
            log(f"Using interface name binding: -I {iface}")
        elif mode == "iface_ip" and (iface_ip or self._source_address):
            # Use IP address binding - prioritize source_address if provided
            if self._source_address:
                cmd.extend(['-i', self._source_address])
                log(f"Using source address binding: -i {self._source_address}")
            elif iface_ip:
                cmd.extend(['-i', iface_ip])
                log(f"Using interface IP binding: -i {iface_ip}")
        elif mode is None:
            # No interface binding - rely on routing only
            log("No interface binding - relying on routing only")
        elif self._source_address:
            # Fallback: Use provided source address
            cmd.extend(['-i', self._source_address])
            log(f"Fallback: Using source address binding: -i {self._source_address}")
        
        # Log the full command for debugging
        log(f"Speedtest command: {' '.join(cmd)}")
        
        # Run the speedtest with Popen for real-time monitoring
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Start timeout killer thread
        killer_thread = ProcessKillerThread(process, self._timeout)
        killer_thread.start()
        
        # Monitor output in real-time
        data, fatal_error = self._monitor_speedtest_output(process)
        
        # If we got a result or fatal error, kill the process immediately (don't wait)
        if data is not None or fatal_error:
            # We have result or fatal error - kill process immediately
            try:
                if process.poll() is None:
                    process.kill()
            except:
                pass
        
        # Wait for process to complete or be killed (should be quick if we killed it)
        process.wait()
        final_returncode = process.returncode
        
        # Wait for killer thread to finish
        killer_thread.join(timeout=1)
        
        # Log detailed failure information if process failed
        if final_returncode != 0 and data is None:
            log(f"Speedtest process exited with return code {final_returncode}")
            if final_returncode == 2:
                log("Return code 2 typically indicates configuration or server connection failure")
            elif final_returncode == -13:
                log("Return code -13 (SIGPIPE) typically indicates broken pipe - connection lost during test")
            elif final_returncode < 0:
                log(f"Negative return code {final_returncode} indicates process was killed by signal {abs(final_returncode)}")
        
        return process, data
    
    def start(self, test_type='both'):
        """Run the actual speedtest using the binary executable
        test_type: 'download', 'upload', or 'both' (default)"""
        try:
            # Check if ookla binary exists, if not try to download it
            if not os.path.exists('ookla'):
                log("Ookla binary not found, attempting to download...")
                # Note: Download logic would go here if needed
                raise Exception("Ookla binary not found")
            
            # Get interface information for routing
            iface, gateway, iface_ip, connection_state = self._get_interface_info()
            
            # If we have source_address but couldn't find interface info, use source_address as iface_ip
            if self._source_address and not iface_ip:
                iface_ip = self._source_address
            
            # Determine initial mode - try interface name first if available
            if iface and not self._source_address and connection_state != "standby":
                mode = "iface"
            elif iface_ip or self._source_address:
                mode = "iface_ip"
            else:
                # No interface info available - try without binding (routing only)
                mode = None
            
            # Reset state
            test_timed_out = False
            test_ended_with_ip = False
            
            # Run speedtest with initial mode
            # Note: Ookla binary always runs full test (download + upload), we filter results based on test_type
            process, data = self._run_speedtest_with_mode(mode, iface, gateway, iface_ip, connection_state, test_type)
            
            # Filter results based on test_type (binary always returns both, we extract what we need)
            if data and test_type == 'download':
                # Keep download, zero out upload
                if 'upload' in data:
                    data['upload'] = {'bandwidth': 0, 'bytes': 0}
            elif data and test_type == 'upload':
                # Keep upload, zero out download
                if 'download' in data:
                    data['download'] = {'bandwidth': 0, 'bytes': 0}
            
            # Check if we need to retry with IP mode
            if not data and mode == "iface" and iface_ip and not test_ended_with_ip:
                log("Test failed with interface name binding, retrying with IP address binding")
                
                # Retry with IP mode
                mode = "iface_ip"
                test_ended_with_ip = True
                
                try:
                    process, data = self._run_speedtest_with_mode("iface_ip", iface, gateway, iface_ip, connection_state, test_type)
                    # Filter results again if we got data
                    if data and test_type == 'download' and 'upload' in data:
                        data['upload'] = {'bandwidth': 0, 'bytes': 0}
                    elif data and test_type == 'upload' and 'download' in data:
                        data['download'] = {'bandwidth': 0, 'bytes': 0}
                except Exception as e:
                    log(f"Retry with IP also failed: {e}")
                    data = None
            
            # Check for partial results even if process failed
            # Ookla binary may return partial results if one direction fails
            has_download = False
            has_upload = False
            
            if data:
                # Extract results - check if download/upload succeeded independently
                download_data = data.get('download', {})
                upload_data = data.get('upload', {})
                
                # Check if bandwidth data exists (not just zero, but actually present)
                download_bandwidth = download_data.get('bandwidth')
                upload_bandwidth = upload_data.get('bandwidth')
                
                # Convert to bits per second if data exists
                download_bps = download_bandwidth * 8 if download_bandwidth is not None else 0
                upload_bps = upload_bandwidth * 8 if upload_bandwidth is not None else 0
                
                # Extract bytes information from the JSON response
                bytes_received = download_data.get('bytes', 0)
                bytes_sent = upload_data.get('bytes', 0)
                ping = data.get('ping', {}).get('latency', 0)
                server = data.get('server', {})
                client = dict(data.get('client') or {})
                # Ookla JSON may have isp at top level instead of under client
                if data.get('isp') and not client.get('isp'):
                    client['isp'] = data.get('isp')
                share_url = data.get('result', {}).get('url', '')
                
                # Check if we have at least one valid result (bandwidth data exists and is > 0)
                has_download = download_bandwidth is not None and download_bandwidth > 0
                has_upload = upload_bandwidth is not None and upload_bandwidth > 0
                
                # Log detailed information about each direction
                if download_bandwidth is None:
                    log("Download test: No bandwidth data received (test may have timed out or failed)")
                elif download_bandwidth == 0:
                    log("Download test: Bandwidth is zero (test completed but no data transferred)")
                elif not has_download:
                    log(f"Download test: Invalid bandwidth value: {download_bandwidth}")
                
                if upload_bandwidth is None:
                    log("Upload test: No bandwidth data received (test may have timed out or failed)")
                elif upload_bandwidth == 0:
                    log("Upload test: Bandwidth is zero (test completed but no data transferred)")
                elif not has_upload:
                    log(f"Upload test: Invalid bandwidth value: {upload_bandwidth}")
                
                if has_download or has_upload:
                    # We have at least one valid result - return partial results
                    isp_str = client.get('isp') or data.get('isp') or ''
                    self.results = SpeedtestResults(
                        download=download_bps if has_download else 0,
                        upload=upload_bps if has_upload else 0, 
                        ping=ping,
                        server=server,
                        client=client,
                        bytes_received=bytes_received,
                        bytes_sent=bytes_sent,
                        isp=isp_str
                    )
                    
                    # Set the share URL
                    self.results._share = share_url
                    
                    # Log if we only got partial results
                    if has_download and not has_upload:
                        log("Warning: Upload test failed, but download results are available")
                    elif has_upload and not has_download:
                        log("Warning: Download test failed, but upload results are available")
                    
                    return self.results
                else:
                    # Neither direction succeeded - log details
                    log(f"Both directions failed: download_bandwidth={download_bandwidth}, upload_bandwidth={upload_bandwidth}")
            
            # If no data and process failed, raise exception
            # But only if we truly have no results (not even partial)
            if process and process.returncode != 0:
                # Only raise exception if we have no partial results
                if not data or (not has_download and not has_upload):
                    error_msg = "Speedtest failed"
                    if process.returncode:
                        error_msg += " with return code %d" % process.returncode
                        # Add helpful context for common error codes
                        if process.returncode == 2:
                            error_msg += " (configuration/server connection issue)"
                        elif process.returncode == -13:
                            error_msg += " (SIGPIPE - connection broken during test)"
                        elif process.returncode < 0:
                            error_msg += f" (killed by signal {abs(process.returncode)})"
                    # Include interface info in error for debugging
                    iface_info = self._get_interface_info()
                    if iface_info[0] or iface_info[2]:
                        error_msg += f" [interface: {iface_info[0] or 'N/A'}, ip: {iface_info[2] or 'N/A'}]"
                    raise Exception(error_msg)
                # If we have partial results, they were already returned above
            
            # If we get here, something went wrong and we have no results
            raise Exception("Speedtest completed but no results were obtained")
            
        except FileNotFoundError:
            raise Exception("Ookla binary not found and download failed")
        except subprocess.TimeoutExpired:
            raise Exception("Speedtest timed out")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse speedtest output: {e}")
        except Exception as e:
            raise Exception(f"Speedtest failed: {e}")
