#!/usr/bin/env bash
set -euo pipefail

: '
A script for the COMMA BODIES to be able to install a real
certbot certificate under a subdomain that resolves to a local ip
and setup an nginx proxy to pass webrtc to other devices with HTTPS.

Usage: ./setup_local_cert.sh <domain>
       ./setup_local_cert.sh --renew <domain>
'

if [ "$1" = "--renew" ]; then
  if [ -z "${2:-}" ]; then
    echo "Usage: $0 --renew <domain>"
    exit 1
  fi
  echo -e "\033[32mRenewing certificate for $2...\033[0m"
  sudo certbot certonly --manual --preferred-challenges dns -d "$2"
  exit 0
fi

if [ -z "$1" ]; then
  echo "Usage: $0 <domain>"
  exit 1
fi

echo "Updating and upgrading system packages..."
sudo apt-get update
sudo apt-get upgrade -y

echo "Installing nginx..."
sudo apt-get install -y nginx

echo "Installing certbot dependencies..."
sudo apt-get install -y python3 python3-dev python3-venv libaugeas-dev gcc

echo "Creating certbot virtual environment..."
sudo python3 -m venv /opt/certbot/

echo "Installing certbot..."
sudo /opt/certbot/bin/pip install certbot certbot-nginx
if [ -L /usr/local/bin/certbot ]; then
  echo "certbot symlink already exists at /usr/local/bin/certbot"
  exit 0
fi
sudo ln -s /opt/certbot/bin/certbot /usr/local/bin/certbot

echo -e "\033[32mRequesting certificate for $1...\033[0m"
sudo certbot certonly --manual --preferred-challenges dns -d "$1"

echo "Writing nginx config..."
sudo tee /etc/nginx/sites-available/default > /dev/null <<EOF
server {
        listen 80 default_server;
        listen [::]:80 default_server;

        listen 443 ssl default_server;
        listen [::]:443 ssl default_server;

        ssl_certificate /etc/letsencrypt/live/$1/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/$1/privkey.pem;

        location /test {
                alias /var/www/html;
                index index.html index.htm index.nginx-debian.html;
                try_files \$uri \$uri/ =404;
        }

        location / {
                add_header 'Access-Control-Allow-Origin' '*' always;
                proxy_hide_header 'Access-Control-Allow-Origin';

                proxy_pass http://127.0.0.1:5001;
                proxy_set_header Host \$host;
                proxy_set_header X-Real-IP \$remote_addr;
                proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto \$scheme;
        }
}
EOF

echo "Reloading nginx..."
sudo nginx -t && sudo systemctl reload nginx



: '
move /var/lib and /var/log to writable location

... in nginx.conf
http {
        access_log /data/nginx/logs/access.log;
        error_log  /data/nginx/logs/error.log;

        client_body_temp_path /data/nginx/body;
        proxy_temp_path       /data/nginx/proxy_temp;
        fastcgi_temp_path     /data/nginx/fastcgi_temp;
        uwsgi_temp_path       /data/nginx/uwsgi_temp;
        scgi_temp_path        /data/nginx/scgi_temp;
...

... then run
sudo mkdir -p /data/nginx/logs
sudo mkdir -p /data/nginx/body
sudo mkdir -p /data/nginx/proxy_temp
sudo mkdir -p /data/nginx/fastcgi_temp
sudo mkdir -p /data/nginx/uwsgi_temp
sudo mkdir -p /data/nginx/scgi_temp

... finally
sudo chown -R comma:comma /data/nginx
'
