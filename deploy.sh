#!/bin/bash
# Deploy script that reads from sdk_settings.ini

APP_NAME=$1
if [ -z "$APP_NAME" ]; then
    echo "Usage: ./deploy.sh <app_name>"
    exit 1
fi

# Update app_name in sdk_settings.ini
sed -i.bak "s/^app_name=.*/app_name=$APP_NAME/" sdk_settings.ini

# Read credentials from sdk_settings.ini
IP=$(grep dev_client_ip sdk_settings.ini | cut -d= -f2)
USER=$(grep dev_client_username sdk_settings.ini | cut -d= -f2)
PASS=$(grep dev_client_password sdk_settings.ini | cut -d= -f2)

echo "Deploying $APP_NAME to $IP..."

python3 make.py purge && \
sleep 2 && \
python3 make.py build $APP_NAME && \
python3 make.py install $APP_NAME && \
sleep 3 && \
echo "Checking logs..." && \
curl -s -u $USER:$PASS http://$IP/api/status/log/ 2>/dev/null | \
python3 -c "import json,sys; logs=json.load(sys.stdin)['data']; [print(l[3]) for l in logs[-20:] if '$APP_NAME' in str(l)]"
