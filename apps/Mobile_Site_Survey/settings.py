settings = {
    "enabled": True,
    "all_wans": False,
    "min_distance": 50,
    "enable_timer": False,
    "min_time": 0,
    "speedtests": True,
    "dead_reckoning": False,
    "packet_loss": True,
    "write_csv": True,
    "debug": False,
    "send_to_server": False,
    "full_diagnostics": False,
    "include_logs": False,
    "server_url": "https://5g-ready.io/injector",
    "server_token": "",
    "enable_surveyors": False,
    "surveyors": [],
    # Speedtest engine: "netperf" (built into NCOS, always available), "iperf3"
    # (needs iperf3_server) or "ookla" (only if an Ookla binary is bundled).
    # On first run this is set to the best engine the build offers, and any
    # engine whose binary is absent falls back to netperf.
    "speedtest_engine": "netperf",
    # iPerf3 target - hostname or IP of your iperf3 server.
    "iperf3_server": "",
    # iPerf3 port or port range, e.g. "5201" or "5201-5210". A range lets
    # concurrent modem tests use separate ports and lets a busy port fall
    # through to the next one.
    "iperf3_ports": "5201-5210",
    # iPerf3 test options. These map directly onto iperf3 command line flags and
    # only apply when speedtest_engine is "iperf3".
    # Transport: "tcp" or "udp" (-u). UDP reports jitter and datagram loss but
    # no latency, and iperf3 caps an unrestricted UDP test at 1 Mbit/s, so set
    # iperf3_bandwidth when using it.
    "iperf3_protocol": "tcp",
    # Seconds per direction (-t). Ignored when iperf3_bytes is set.
    "iperf3_duration": 10,
    # Simultaneous streams (-P). More streams fill a high latency link faster.
    "iperf3_parallel": 1,
    # Target rate (-b), e.g. "50M". Blank is unlimited for TCP.
    "iperf3_bandwidth": "",
    # Transfer a fixed volume (-n) instead of testing for a fixed time, e.g.
    # "100M". Blank uses iperf3_duration.
    "iperf3_bytes": "",
    # Read/write buffer length (-l), e.g. "128K". Blank uses the iperf3 default.
    "iperf3_buffer_length": "",
    # Seconds to discard from the start of each direction (-O), so TCP slow
    # start does not drag the average down.
    "iperf3_omit": 0,
    # Socket buffer / TCP window size (-w), e.g. "512K". Blank is autotuned.
    "iperf3_window": "",
    # Disable Nagle's algorithm (-N). TCP only.
    "iperf3_no_delay": False,
    # Use sendfile() instead of copying through userspace (-Z), which lowers
    # router CPU on fast links. TCP only.
    "iperf3_zero_copy": False
}
