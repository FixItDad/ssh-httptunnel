# ssh-httptunnel
Provides SSH connectivity to a remote server through an HTTP connection.
* Allows SSH and file transfers (SCP / SFTP) to the remote system.
* Supports HTTP proxy on the client side
* Requires Python 2.7 on both sides

This was written to allow access to a remote network from a restrictive client network environment. It was written for a Linux environment on both the client and server side. Tries to use only standard Python libraries since that was what was available in the environment.
## Architecture
The ssh-httptunnel client provides a local SSH connection point. When an SSH client connects, a connection is made via HTTPS to an HTTP server in the remote environment. This server authenticates the client connection and proxies the traffic to the ssh-httptunnel server. The server component then connects to the target SSH server. Once the SSH connection is established, normal SSH port forwarding, or other traffic can be set up. SFTP and SCP also work.

## Security Notes
* Relies on a third party HTTP server to provide a SSL/TLS connection as well as authentication / authorization. NGINX was used due to it's lightweight system requirements.
* Does NOT validate the server SSL/TLS certificate. This functionality was not readily available in the standard Python libraries at the time of writing. This could allow Man In The Middle (MITM) attacks.
* The client is written to use HTTP Basic authenticiation.
* The client stores configuration information including passwords in an AES encrypted file with password based key derivation function (PBKDF2) to generate the encryption key.
