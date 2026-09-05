# Desktop OAuth security boundary

The server OAuth callback exemption is not a desktop exemption.  In desktop runtime,
every `/v1/` route requires the ephemeral loopback IPC bearer before any server OAuth
or public-route exemption is considered.  The beta exposes no unauthenticated OAuth
bootstrap surface.  Any future native desktop OAuth flow requires an explicit security
design; adding a route to the server callback allowlist cannot make it public in the
desktop sidecar.
