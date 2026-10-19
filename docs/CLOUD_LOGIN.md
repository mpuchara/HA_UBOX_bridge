# UBox cloud login implementation

Based on independently documented UBox API interactions, not an official SDK:
- POST https://portal.ubianet.com/api/v3/login
- POST https://portal.ubianet.com/api/v2/user/device_list

A login session is used to read camera metadata and device authentication information for accessing your own cameras. The token and camera password are held in memory only; the Home Assistant options contain the account login locally (HA add-on configuration). No password or token is returned from the dashboard status API. HTTPS certificate verification is enabled.

When one device exists, it is selected automatically. With multiple devices, set uid in the add-on configuration. If the account authenticates through Google/Apple rather than email/password, this mode may not work.

A camera snapshot still requires P4P video capture via the pinned upstream client. Compatibility with XEGA XG-01-EU4G, firmware 2068.0.13.47, remains untested. Cloud API changes can break discovery. Avoid aggressive polling on solar devices.
