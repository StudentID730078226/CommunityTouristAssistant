# Deployment Guide

This guide walks through deploying the Community Tourist Assistant from scratch.
It includes local setup, PostgreSQL configuration, and a production deployment using
Gunicorn and Nginx. Adjust hostnames and paths to your environment.

## Prerequisites

- Python 3.11+ and pip
- PostgreSQL 15+ (or SQLite for local-only testing)
- Git

## Local Setup (Development)

1. Clone the repository and create a virtual environment.
   ```bash
   git clone <repo-url>
   python -m venv venv
   .\venv\Scripts\activate
   ```

2. Install dependencies.
   ```bash
   pip install -r requirements.txt
   ```

3. Create a local `.env` file (copy `.env.example`).
   ```bash
   copy .env.example .env
   ```

4. Apply migrations and create an admin account.
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

5. Run the development server.
   ```bash
   python manage.py runserver
   ```

## PostgreSQL Setup

1. Create a database and user.
   ```sql
   CREATE DATABASE community_tourism;
   CREATE USER tourism_user WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE community_tourism TO tourism_user;
   ```

2. Update `.env` with PostgreSQL credentials.
   ```
   DB_ENGINE=django.db.backends.postgresql
   DB_NAME=community_tourism
   DB_USER=tourism_user
   DB_PASSWORD=your_password
   DB_HOST=localhost
   DB_PORT=5432
   ```

3. Apply migrations.
   ```bash
   python manage.py migrate
   ```

## Static and Media Files

1. Confirm `STATIC_ROOT` and `MEDIA_ROOT` in `settings.py`.
2. Collect static files for production.
   ```bash
   python manage.py collectstatic
   ```

## Production Deployment (Gunicorn + Nginx)

1. Install system packages.
   ```bash
   sudo apt update
   sudo apt install python3-venv python3-pip nginx
   ```

2. Create an app directory and virtual environment.
   ```bash
   sudo mkdir -p /srv/community_tourism
   sudo chown $USER:$USER /srv/community_tourism
   cd /srv/community_tourism
   git clone <repo-url> .
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Configure environment variables.
   ```bash
   cp .env.example .env
   nano .env
   ```

4. Run migrations and collect static files.
   ```bash
   python manage.py migrate
   python manage.py collectstatic
   ```

5. Test Gunicorn locally.
   ```bash
   gunicorn community_tourism.wsgi:application --bind 0.0.0.0:8000
   ```

## Systemd Service

Create a systemd unit file at `/etc/systemd/system/community_tourism.service`:

```
[Unit]
Description=Community Tourist Assistant
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/srv/community_tourism
EnvironmentFile=/srv/community_tourism/.env
ExecStart=/srv/community_tourism/venv/bin/gunicorn community_tourism.wsgi:application --bind 127.0.0.1:8000

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable community_tourism
sudo systemctl start community_tourism
```

## Nginx Configuration

Create `/etc/nginx/sites-available/community_tourism`:

```
server {
    listen 80;
    server_name your-domain.com;

    location /static/ {
        alias /srv/community_tourism/staticfiles/;
    }

    location /media/ {
        alias /srv/community_tourism/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site and reload Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/community_tourism /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## HTTPS (Recommended)

Use Certbot to add a TLS certificate:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Operational Tasks

- Backups: schedule nightly PostgreSQL dumps.
- Logs: monitor Gunicorn and Nginx logs for errors.
- Updates: pull latest code, run migrations, restart the service.

