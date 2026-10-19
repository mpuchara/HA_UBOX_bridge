# Local Windows installer (no GitHub Pages required)

1. Download the ZIP from the CYD installer GitHub Release or from a completed
   **Build and publish CYD browser installer** workflow artifact.
2. Extract all files to one folder (do not run from ZIP preview).
3. Connect classic ESP32-2432S028 CYD via USB.
4. Double-click `Start-Installer.cmd`. This runs the checked-in
   `Install-CYD.ps1`, which starts a GET-only file server bound to
   **127.0.0.1**, opens Edge at `http://127.0.0.1:8765`.
5. Select COM4 in ESP Web Tools and confirm firmware flashing.
6. After reboot the device displays a randomized setup hotspot password;
   use `http://192.168.4.1` to set 2.4GHz Wi-Fi, HA IP and snapshot token.

No Python, PlatformIO or admin permissions are needed. Browser must have
internet access to load ESP Web Tools from unpkg.com. Loopback is a
potentially trustworthy Web Serial origin in modern Chrome/Edge.

**Security:** USB flashing overwrites the existing application and may
erase the current ESP32 configuration. The local HTTP server accepts only
GET requests for a fixed allowlist of bundled paths and binds exclusively
to loopback. Review scripts before running.
