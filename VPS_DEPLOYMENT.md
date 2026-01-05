# VPS Deployment Guide (Vultr / Ubuntu)

This guide walks you through deploying **FakturaScanner** on a fresh Ubuntu VPS (e.g., from Vultr, DigitalOcean, Linode).

## Prerequisites
*   A VPS running **Ubuntu 22.04 LTS** or newer.
*   SSH access to the server.
*   A domain name (optional, but recommended for SSL).

## 1. Initial Server Setup
Connect to your server via SSH:
```bash
ssh root@your_server_ip
```

Update the system:
```bash
apt update && apt upgrade -y
```

## 2. Install Docker & Docker Compose
We will use the official installation script for convenience:
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```
Verify installation:
```bash
docker --version
docker compose version
```

## 3. Deploy the Application

### Option A: Clone from Git (Recommended)
1.  Clone your repository (replace with your actual repo URL):
    ```bash
    git clone https://github.com/your-username/faktura_scanner_flask.git
    cd faktura_scanner_flask
    ```
2.  Create the data directory:
    ```bash
    mkdir data
    ```
3.  Start the application:
    ```bash
    docker compose up -d --build
    ```

### Option B: Upload Files Manually (SCP/SFTP)
If you don't use Git, copy your project files to the server (e.g., to `/opt/faktura-scanner`) and run `docker compose up -d`.

## 4. Verify Deployment
The application should now be running on port **8083**.
Visit: `http://your_server_ip:8083`

## 5. (Recommended) Set up Nginx & SSL (HTTPS)
Exposing port 8083 directly is fine for testing, but for production, you should use Nginx as a reverse proxy with a standard port (80/443) and an SSL certificate.

1.  **Install Nginx & Certbot:**
    ```bash
    apt install -y nginx certbot python3-certbot-nginx
    ```

2.  **Configure Nginx:**
    Create a new config file:
    ```bash
    nano /etc/nginx/sites-available/faktura-scanner
    ```
    Paste this configuration (replace `your-domain.com`):
    ```nginx
    server {
        listen 80;
        server_name your-domain.com;

        location / {
            proxy_pass http://localhost:8083;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            client_max_body_size 16M;
        }
    }
    ```

3.  **Enable Site:**
    ```bash
    ln -s /etc/nginx/sites-available/faktura-scanner /etc/nginx/sites-enabled/
    rm /etc/nginx/sites-enabled/default
    nginx -t
    systemctl restart nginx
    ```

4.  **Get SSL Certificate:**
    ```bash
    certbot --nginx -d your-domain.com
    ```

Now your app is accessible securely at `https://your-domain.com`.

## 6. Maintenance
*   **View Logs:** `docker compose logs -f`
*   **Stop App:** `docker compose down`
*   **Update App:**
    ```bash
    git pull
    docker compose up -d --build
    ```
*   **Backup:** Back up the `data/`, `uploads/`, and `pdfs/` directories regularly.
