REM ['runas', '/user:lily-lyn\\Administrator', 'netsh', 'interface', 'ip', 'set', 'address',
REM '"Local Addin ENet"', 'static', '192.168.115.6', '255.255.255.0']

runas /noprofile /user:lily-lyn\lynn "netsh interface ip set address \"ENet USB-1\" static 192.168.1.6 255.255.255.0"
