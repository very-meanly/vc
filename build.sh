#!/bin/bash

sudo apt install -y python3-venv ffmpeg zip wget curl ca-certificates redis-server redis-tools supervisor nginx
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt/ 'lsb_release -cs'-pgdg main" >> /etc/apt/sources.list.d/pgdg.list'
sudo apt update -y
sudo apt install -y postgresql postgresql-contrib
sudo snap install node --classic
sudo npm install -g npm@latest
sudo npm install -g npx
sudo npm install -g n
sudo n latest
npm install

./build.local.sh

sudo -u postgres createuser -d vc -P
sudo -u postgres createdb -O vc vc

sudo cp nginx.unsecure.conf /etc/nginx/sites-enabled/vc.conf
sudo cp supervisor.conf /etc/supervisor/conf.d/vc.conf

sudo systemctl enable nginx
sudo systemctl start nginx

sudo systemctl enable supervisor
sudo systemctl start supervisor