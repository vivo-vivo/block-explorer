# block explorer
Block Explorer

VIVO Blockchain Explorer v1.0.79 — PORTABLE SOURCE TEMPLATE
=========================================================

IMPORTANT
---------
This ZIP contains a source snapshot of the deployed v1.0.79 PHP frontend and
Python API, with a manifest and documentation. It is NOT a drop-in explorer for
arbitrary currencies. The backend uses VIVO/Dash-family RPCs, quorum and DKG
methods, block structure and address assumptions. Adapting to another coin
requires code changes, especially for Bitcoin-like non-Dash coins.

The packager copies only the two audited source files, NOT any /etc configuration,
wallets, node datadirs, authentication cookies, private keys, logs, DB data, or
existing systemd service overrides. It refuses output if it detects credential
patterns in the source. This is a conservative scanner, not a formal secret audit;
review files yourself before distributing.

WHAT IS IN THE ZIP
------------------
web/index.php             PHP explorer frontend
api/explorer-api.py       Python HTTP API (existing Unix socket model)
CONFIG-PLACEHOLDERS.example  Template values, NOT used automatically by code
EXAMPLE-systemd-service.txt Service example, NOT an installed production unit
SOURCE-MANIFEST.json      SHA-256 checksums of original source
README-INSTALL.txt        This guide

SYSTEM REQUIREMENTS
-------------------
- Ubuntu 24.04 LTS recommended; other Linux may need package name adjustments.
- Apache HTTP Server 2.4 with PHP 8.3 or later + PHP cURL module.
- Python 3.12+ standard library for API (actual source imports should be reviewed).
- A FULLY SYNCED and compatible coin daemon with local read-only CLI/RPC access.
- systemd for service management, curl for diagnostics, zip/unzip to transfer.
- TLS certificate for the explorer hostname (e.g. via certbot).
- A local Unix socket protected so the API is not accessible publicly.

Install baseline on Ubuntu 24.04:
 sudo apt update
 sudo apt install -y apache2 php libapache2-mod-php php-curl python3 \
     curl unzip ca-certificates

Do not enable or restart any production service merely by running these commands.
Other coin nodes may have their own build, runtime, and database requirements.

HOW TO PACKAGE ON THE ORIGINAL VPS
----------------------------------
1. Copy the packager kit onto vps3570282 (e.g. /root/vivo-explorer-portable-packager).
2. Verify the script and read it before executing:
   python3 -m py_compile BUILD_PORTABLE_ZIP.py
   python3 BUILD_PORTABLE_ZIP.py
   python3 BUILD_PORTABLE_ZIP.py --apply
3. The output is /root/VIVO-Explorer-v1.0.79-portable-source.zip.
4. Verify SHA-256 and archive entries:
   sha256sum /root/VIVO-Explorer-v1.0.79-portable-source.zip
   unzip -l /root/VIVO-Explorer-v1.0.79-portable-source.zip
5. Copy the ZIP to your desktop using scp/SFTP; do not publish until reviewed.

INSTALL ON ANOTHER VPS — GUIDED ADAPTATION
-----------------------------------------
1. Create a new disposable test VPS (not an existing wallet, production node,
   or masternode) and install the requirements above.
2. Upload the portable ZIP, extract it under /root or /opt/staging, and review
   SOURCE-MANIFEST.json and source files.
3. Copy Python API to /opt/coin-explorer/explorer-api.py; copy frontend to
   /var/www/coin-explorer/public/index.php. Ensure Apache can read the PHP but
   cannot write to the source files; restrict API filesystem permissions.
4. Adapt the API RPC invocation: the existing API may expect `vivo-cli`, specific
   chain paths, socket location, timeouts and VIVO-specific RPC methods. Replace
   with the correct coin daemon commands and test each endpoint in isolation.
5. Adapt the PHP `api()` function's CURLOPT_UNIX_SOCKET_PATH to the socket the
   adapted backend binds. The original source uses
       /run/vivo-explorer/explorer.sock
   and the example generic path is
       /run/coin-explorer/explorer.sock
6. Adapt coin name, ticker, domain links, block formats, time conversions,
   transaction fee logic, address prefixes/checksum validation and network
   specific features. For coins without Dash-family quorums/DKG, remove or
   disable their navigation, routes and RPC calls in an isolated working copy.
7. Review and adapt EXAMPLE-systemd-service.txt. Create a dedicated unprivileged
   account with access to only what's necessary. Confirm the API source has a
   runnable main entry point and the socket is reachable by the web-server group.
   The sample is NOT guaranteed ready to start without these changes.
8. Give the Apache virtual host a DocumentRoot pointing to the frontend's web
   directory. Configure HTTPS. Keep the Unix socket private; never publicly
   expose daemon RPC, its cookie or administrative APIs.
9. Test local PHP syntax and Python syntax before starting services:
       php -l /var/www/coin-explorer/public/index.php
       python3 -m py_compile /opt/coin-explorer/explorer-api.py
   Test API status, block by height, block by hash, transaction search, invalid
   search, and unsupported endpoint responses with synthetic and real data.
10. Test via curl -I https://explorer.example.com/ and use browser tests.
    Verify no RPC secrets, headers, logs or internal paths leak in any response.
11. Only after end-to-end acceptance on the test VPS, enable the new API service
    and public Apache site. Use a rollback backup for each production release.

SECURITY / SECRETS
------------------
- Never put RPC_PASSWORD or RPC_USER into the PHP source or version-control repo.
- Prefer local cookie-based node authentication or a root-controlled credentials
  file readable only by the dedicated API service account. Never publish it.
- The CONFIG-PLACEHOLDERS.example file is documentation, not a real .env reader.
- Do not copy /root/.vivocore, /etc/vivo*, ~/.cookie, vivo.conf, wallet.dat,
  BLS operator keys, masternode keys, SSH keys, DBs or production systemd
  overrides into the distributed archive.
- Do not enable RPC over a publicly accessible TCP socket.
- A private source review is essential; the scanner cannot detect all secrets.

KNOWN LIMITATIONS OF ORIGINAL v1.0.79
------------------------------------
- The VIVO address-index / balance / rich-list features are disabled.
- Quorum/DKG display is VIVO/Dash-specific and is not proof of signing health.
- Original frontend maps non-200 API replies to null, so missing records and
  backend failures can produce a combined visitor message.
- The frontend search limits input to 75 bytes and shows an error for oversized
  inputs. The underlying API may have different length constraints.
- RPC compatibility and service unit behavior must be revalidated per coin.

VERIFIED V1.0.79 SOURCE HASHES (ORIGINAL, BEFORE ANY CUSTOMIZATION)
-------------------------------------------------------------------
web/index.php          93b470a756e691e410c3dad23c7b3046f346b5345fe5bea76c7f431d8af299ba
api/explorer-api.py    a7e1b157b7b9eae5856c09f7134c7898be3aa558c8ec4c818bb646a56d659947

Nothing in this packager should modify or restart the original production
explorer, VIVO daemon, Apache, masternodes, or quorum code.
