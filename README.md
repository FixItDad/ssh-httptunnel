# ssh-httptunnel
Provides SSH connectivity to a remote server through an HTTP connection.
* Allows SSH and file transfers (SCP / SFTP) to the remote system.
* Supports authenicated HTTP proxy on the client side
* Requires Python 2.7 on both sides

This was written to allow access to a remote network from a restrictive client network environment. It was written for a Linux environment on both the client and server side, but should be fairly easy to adapt to other systems. Tries to use only standard Python libraries since that was what was available in the environment.

## Architecture
![alt text](https://github.com/FixItDad/ssh-httptunnel/raw/master/docs/architecture.jpg "Architecture diagram showing connection flow from an SSH client to the local ssh-httptunnel client though an optional HTTP to the Internet. The connection hits an HTTP server on the target network side and is proxied to the ssh-httptunnel server which connects to an SSH server on the local network to complete the SSH connection.")

The ssh-httptunnel client provides a local SSH connection point. When an SSH client connects, a connection is made via HTTPS to an HTTP server in the remote environment. This server authenticates the client connection and proxies the traffic to the ssh-httptunnel server. The server component then connects to the target SSH server. Once the SSH connection is established, normal SSH port forwarding, or other traffic can be set up. SFTP and SCP also work.

## Security Notes
* Relies on a third party HTTP server to provide a SSL/TLS connection as well as authentication / authorization. NGINX was used due to its lightweight system requirements.
* Does NOT validate the server SSL/TLS certificate. This functionality was not readily available in the standard Python libraries at the time of writing. This could allow Man In The Middle (MITM) attacks on the HTTPS layer. However, SSH provides an additional robust encryption layer.
* The client is written to use HTTP Basic authenticiation.
* The client stores configuration information including passwords in an AES encrypted file with password based key derivation function (PBKDF2) to generate the encryption key.

## Client Installation
The client system should have Python 2 (2.7 or later) installed. The client has only been tested on Linux.  
An installer is not provided. Copy client.py and configfile.py to a directory of your choosing preferably in your execution path. You can make it executable or run it using the python command (**python client.py**)

## Client configuration
The listen port for the client and config file location can be changed near the top of the client.py executable. 
```python
# listen for clients on this local port.
LISTEN_PORT= 8022

# Configuration filename in users home directory.
configFilename = '.config/httpclient.conf'
```
Credentials and network configuration are entered the first time the program is run. You will be prompted twice for a password for the configration file. This password will need to be entered each time client.py is started. The configuration can later be changed by running **client.py config** . The following items are configurable:
1. **Proxy IP (optional)** - Ip address or hostname of Internet proxy
2. **Proxy username and password** - credentials for an authenticating proxy
1. **VPN URL** - The URL for the target ssh-httptunnel server
1. **VPN username and password** - credentials for the target server

## Server installation
You will need Python 2 (2.7 or later) installed to run the server. You will also need a reverse proxy for authentication and HTTPS support.

An Ansible playbook is provided to help set up the server side. It assumes that the server will run under a dedicated user behind an NGINX reverse proxy. Please see NGINX configuration instructions elsewhere to configure SSL/TLS for your server. DO NOT RUN THIS SERVER OVER HTTP. See Let's Encrypt if you want a free, maintenance-free TLS certificate setup.

If you are familiar with Ansible, the file layout may seem weird. I got tired of having too many main.yml files open in my editor and opted for a different file layout that I like better. The hosts.ini file contains variables that may be used to configure the ssh-httptunnel server.

If you are not familiar with Ansible or don't want to use it, start by looking at the ansible/roles/ssh-httptunnel/ssh-httptunnel.tasks file. It sets up a new httptunnel user, copies the server executable in place, modifies the configuration variables in the executable script, installs a startup script in /etc/init.d and inserts a location block in the NGINX configation file and reloads the NGINX configuration.
