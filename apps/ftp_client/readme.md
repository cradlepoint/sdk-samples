# ftp_client
A sample SDK app that demonstrates uploading a file to an FTP server using Python's built-in `ftplib` module. Creates a test file locally and uploads it to a remote FTP server.

## How It Works

1. Creates a local text file (`my_file.txt`) with sample content
2. Connects to an FTP server
3. Logs in with provided credentials
4. Uploads the file to the server's `/upload/` directory

## Default Configuration

The sample uses a public FTP test server:

| Setting | Value |
|---------|-------|
| Server | `speedtest.tele2.net` |
| Username | `anonymous` |
| Password | `anonymous` |
| Upload directory | `/upload/` |
| Local filename | `my_file.txt` |
| Remote filename | `a.txt` |

## Customizing for Your Server

Edit `ftp_client.py` and update the following:

```python
ftp = FTP('your-ftp-server.com')
reply = ftp.login('your_username', 'your_password')
ftp.cwd('/your/upload/path/')
```

## Sample Output

```
Starting...
FTP login reply: 230 Login successful.
FTP STOR reply: 226 Transfer complete.
```

If the connection fails, the app logs the exception:

```
Starting...
Exception occurred! exception: [Errno -2] Name or service not known
```

## Requirements

- Router firmware 7.26 or later
- Network connectivity to the FTP server
- Valid FTP credentials with write permission on the target directory
- `ftplib` is included in the router's Python environment

## Notes

- The app runs once and exits (restart is set to false in package.ini)
- Ensure the router's WAN connection is active before the app starts
- For production use, consider storing credentials in SDK appdata rather than hardcoding them
