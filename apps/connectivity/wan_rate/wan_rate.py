# WAN Rate Tracker - Monitors and tracks average WAN bandwidth rates over time
import cp
import time
import json

# Configuration with defaults
def get_config(key, default):
    """Get configuration value from appdata or return default."""
    try:
        value = cp.get_appdata(key)
        if value is not None:
            if key in ['wan_rate_buffer_size', 'wan_rate_poll_interval', 'wan_rate_report_interval']:
                return int(value)
            elif key == 'wan_rate_output_path':
                return str(value)
        return default
    except:
        return default

# Initialize configuration
max_samples = get_config('wan_rate_buffer_size', 30)
interval = get_config('wan_rate_poll_interval', 10)
update_interval = get_config('wan_rate_report_interval', 300)  # 5 minutes
field_path = get_config('wan_rate_output_path', '/config/system/asset_id')

# Global variables
samples = []
last_update = time.time()

cp.log(f'WAN Rate Tracker starting: samples={max_samples}, interval={interval}s, update={update_interval}s')

def add_sample(ibps, obps):
    """Add a new bandwidth sample."""
    global samples
    samples.append((ibps, obps))
    
    # Keep only the most recent samples
    if len(samples) > max_samples:
        samples.pop(0)

def calculate_averages():
    """Calculate average bandwidth from collected samples."""
    if not samples:
        return (0.0, 0.0)
    
    total_ibps = sum(sample[0] for sample in samples)
    total_obps = sum(sample[1] for sample in samples)
    count = len(samples)
    
    avg_ibps = total_ibps / count
    avg_obps = total_obps / count
    
    return (avg_ibps, avg_obps)

def format_bandwidth(bps):
    """Format bandwidth with appropriate unit."""
    if bps >= 1000000000:  # >= 1 Gbps
        return f"{round(bps / 1000000000, 1)} Gbps"
    elif bps >= 1000000:   # >= 1 Mbps
        return f"{round(bps / 1000000, 1)} Mbps"
    elif bps >= 1000:      # >= 1 Kbps
        return f"{round(bps / 1000, 1)} Kbps"
    else:
        return f"{round(bps, 1)} Bps"

def update_field(avg_ibps, avg_obps):
    """Update the configured field with average bandwidth data."""
    try:
        # Format with appropriate units
        ibps_formatted = format_bandwidth(avg_ibps)
        obps_formatted = format_bandwidth(avg_obps)
        
        # Create human-readable format with Unicode arrows
        human_readable = f"↓ {ibps_formatted}, ↑ {obps_formatted}"
        
        # Store in the configured field
        result = cp.put(field_path, human_readable)
        
        if result and result.get('status') == 'ok':
            cp.log(f'Updated {field_path} with average rates: {human_readable}')
        else:
            cp.log(f'Failed to update {field_path}: {result}')
            
    except Exception as e:
        cp.log(f'Error updating field {field_path}: {e}')

# Main loop
try:
    while True:
        start_time = time.time()
        
        # Get current WAN stats
        ibps = cp.get('status/wan/stats/ibps')
        obps = cp.get('status/wan/stats/obps')
        if ibps is not None and obps is not None:
            add_sample(ibps, obps)
            
            # Check if we should update the field
            if time.time() - last_update >= update_interval:
                avg_ibps, avg_obps = calculate_averages()
                update_field(avg_ibps, avg_obps)
                last_update = time.time()
        else:
            cp.log('No WAN stats available, skipping this cycle')
        
        # Calculate sleep time to maintain interval
        elapsed = time.time() - start_time
        sleep_time = max(0, interval - elapsed)
        
        if sleep_time > 0:
            time.sleep(sleep_time)
            
except KeyboardInterrupt:
    cp.log('WAN Rate Tracker stopped by user')
except Exception as e:
    cp.log(f'WAN Rate Tracker error: {e}')
    raise
