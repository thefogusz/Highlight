# Chrome connection (Windows, local preview)

Direct downloading remains the default. The optional extension provides the current YouTube session through Chrome Native Messaging when enabled. This is a local preview, not a Chrome Web Store release; successful unit tests do not establish YouTube download success.

## Install once

Run `python scripts/install_browser_bridge.py` with the Highlight runtime after installing this package. In Chrome, open Extensions, enable Developer mode, choose Load unpacked and select `integrations/chrome`. Open the Highlight extension and click the Thai consent/connect button. Keep Chrome open. The popup reports connected only after a native host response. Ordinary users should receive a reviewed Web Store release later; there is no published store URL yet.

## Data flow

Worker creates a short-lived request for one running job. The extension reads only youtube.com cookies with Chrome's supported API and sends them through the allowlisted native messaging pipe. The host rejects stale requests, wrong nonces, unrelated domains and oversized frames. Session payloads are encrypted using Windows current-user DPAPI. The downloader decrypts into memory, validates the exact source URL and uses an in-memory cookie jar. No session values are exposed through MCP, chat, HTTP endpoints or plaintext cookie files. The worker removes the handoff file after success/failure/cancellation. An interrupted process may leave encrypted data, which expires after one hour. Disable in the popup to delete cached handoffs and stop future session transfers.

This avoids externally reading Chrome's locked/encrypted cookie database. YouTube can still reject the resulting request; do not promise success until an actual source file is downloaded and probed.

References: https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging and https://developer.chrome.com/docs/extensions/reference/api/cookies

## Verified local trial (2026-09-22)
With the extension enabled in Chrome, job job_2e2942d2807b424cb3673a6b70854755 downloaded DOM9gelySKc successfully: 882,384,762 bytes, 8292.154 seconds, 1920x1080 AV1 video and Opus audio. FFmpeg decoded samples at the beginning and end. The user requested stopping after download; the job was cancelled before further analysis. This verifies this source and session, not universal YouTube availability or a full-file decode.

## Guided setup through MCP

Call `highlight_browser_setup` with `action: status` and the original `job_id`. Status never reads cookies or changes browser settings. `setup_required` means local host/files are missing; call `action: prepare` to register the current runtime and unpack the bundled extension to the returned absolute folder. Show the returned steps to the user. Chrome installation and session consent remain user actions. `not_connected` does not distinguish an absent extension from closed Chrome or disabled connection. A fresh native-host heartbeat returns `connected`, not proof of YouTube access. Recheck status after consent, then retry the same failed ingest job only when authorized. Cancelled/completed jobs are never resumed by the setup tool. The connector currently supports Windows only.
