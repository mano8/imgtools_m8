# Docker with SSL and an nginx reverse proxy

Running your ASP.NET Core (or other) application in Docker using SSL should not be an overwhelming task.  These steps should do the trick.

Run the following steps from a Linux terminal (I used WSL or WSL2 on Windows from the [Windows Terminal](https://www.microsoft.com/en-us/p/windows-terminal/9n0dx20hk701)).

# 1. Create a `conf` file with information about the cert you'll be creating
It should look something like the content below; call it `my-site.conf` or something like that.

```
[req]
default_bits       = 2048
default_keyfile    = localhost.key
distinguished_name = req_distinguished_name
req_extensions     = req_ext
x509_extensions    = v3_ca

[req_distinguished_name]
countryName                 = Country Name (2 letter code)
countryName_default         = US
stateOrProvinceName         = State or Province Name (full name)
stateOrProvinceName_default = Minnesota
localityName                = Locality Name (eg, city)
localityName_default        = Woodbury
organizationName            = Organization Name (eg, company)
organizationName_default    = KnowYourToolset
organizationalUnitName      = organizationalunit
organizationalUnitName_default = Development
commonName                  = Common Name (e.g. server FQDN or YOUR name)
commonName_default          = localhost
commonName_max              = 64

[req_ext]
subjectAltName = @alt_names

[v3_ca]
subjectAltName = @alt_names

[alt_names]
DNS.1   = localhost
DNS.2   = 127.0.0.1
```

# 2. Use `openssl` to create  `cer` and `key` files
The `my-site.conf` value is specifying the `conf` file you created in step 1.
Make sure to replace `YourStrongPassword` with something of your own choosing.  

```
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout my-site.key -out my-site.crt -config my-site.conf -passin pass:YourStrongPassword
```

**Alternatively,** create a CSR file if you have your own authority with a command as follows:
```
sudo openssl req -out my-site.csr -newkey rsa:4096 -nodes -config my-site.conf 
```
If you have your own authority and it's already trusted, you can skip steps 3 and 4 below.

# 3. Export a `pfx` that you can import / trust
Run the following command to create a `pfx` file.

You'll be prompted for the `YourStrongPassword` value you provided in step 2.

```
sudo openssl pkcs12 -export -out my-site.pfx -inkey my-site.key -in my-site.crt
```

# 4. Import the `pfx` file as a trusted certificate
This step will differ on Mac, Windows, and Linux.  Just follow the steps to import the `pfx` file as a trusted certificate 
on your machine.

# 5. Create the `nginx.Dockerfile` and `nginx.conf` files
These files will set up your nginx image with your certificate files and also provide configuration that performs the 
SSL-based reversed proxy to your own container image.

### `nginx.Dockerfile`
This file defines the image that you will be using and gets your certificate files onto it.

```
FROM nginx:latest

COPY nginx.conf /etc/nginx/nginx.conf
COPY my-site.crt /etc/ssl/certs/my-site.crt
COPY my-site.key /etc/ssl/private/my-site.key
```
### `nginx.conf`
This file defines the configuration for nginx that the reverse proxy will use.

A couple of key points on this file:
* The `server_name` value should be the FQDN / DNS name you provided for the common name in your my-site.conf above (e.g. www.mycoolapi.com)
* The reverse proxy defined here will be listening on port 80 *and* port 443 - if you want to change that tweak the `listen` lines below
* It does upgrades from http/80 to https/443
* The `upstream web-api` defined is used ONLY in this file, but it references `server api:5000` - this will need to be defined in a `docker-compose` file that you create (see next step)
* You can define multiple servers here - if you have an API, a UI, an IdentityServer, or whatever, this reverse proxy can serve them all.  You need multiple `upstream` sections and multiple `server` sections to define them.

```
worker_processes 1;

events { worker_connections 1024; }

http {

    sendfile on;
    large_client_header_buffers 4 32k;

    upstream web-api {
        server api:5000;
    }

    server {
        listen 80;
        server_name my-site;

        location / {
            return 301 https://$host$request_uri;
        }
    }

    server {
        listen 443 ssl;
        server_name my-site;

        ssl_certificate /etc/ssl/certs/my-site.crt;
        ssl_certificate_key /etc/ssl/private/my-site.key;

        location / {
            proxy_pass         http://web-api;
            proxy_redirect     off;
            proxy_http_version 1.1;
            proxy_cache_bypass $http_upgrade;
            proxy_set_header   Upgrade $http_upgrade;
            proxy_set_header   Connection keep-alive;
            proxy_set_header   Host $host;
            proxy_set_header   X-Real-IP $remote_addr;
            proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header   X-Forwarded-Proto $scheme;
            proxy_set_header   X-Forwarded-Host $server_name;
            proxy_buffer_size           128k;
            proxy_buffers               4 256k;
            proxy_busy_buffers_size     256k;
        }
    }
}
```

# 6. Create the `docker-compose.yml` file that ties it all together
This file references your Dockerfile(s) for the various projects you have created.

The `reverseproxy` should point to the `nginx.Dockerfile` you created above.  The ports for that should match the `listen` values from the `nginx.conf` file you created.

The `api` should be named consistently with the `server` value for the `upstream` setting in the `nginx.conf` file and should expose
the same port.  `MyWebApiProject` is your project name or directory name for where the API (or whatever) Dockerfile is.

```
version: '3.7'

services:
  reverseproxy:
    build:
      context: .
      dockerfile: nginx/nginx.Dockerfile
    ports:
      - "443:443" 
      - "80:80" 
    restart: always

  api:
    depends_on:
      - reverseproxy 
    build:
      context: .
      dockerfile: MyWebApiProject/Dockerfile
    environment:
      - ASPNETCORE_URLS=http://*:5000      
    ports:
      - "5000:5000"  
    restart: always
```  

# 7. Add `HOSTS` file entries if you are using DNS names (not localhost)

These would just be records that alias `127.0.0.1` (localhost) to the DNS name you provided in your `my-site.conf` file above.