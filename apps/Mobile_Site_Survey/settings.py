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
    "iperf3_ports": "5201-5210"
}
