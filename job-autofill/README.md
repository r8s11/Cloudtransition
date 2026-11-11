# Job autofill

Chrome extension (MV3) plus a local Python helper that fills job-application forms on Greenhouse, Lever, Ashby, Workday, Indeed and iCIMS from your resume. Design and acceptance cases: [`docs/plans/job-autofill-extension/`](../docs/plans/job-autofill-extension/).

## Install

1. Chrome → `chrome://extensions` → turn on **Developer mode** → **Load unpacked** → pick `job-autofill/extension/`.
2. Start the helper (stdlib Python 3, binds `127.0.0.1:8766` only):

   ```sh
   python3 job-autofill/helper/server.py serve
   ```

3. Pair: run `python3 job-autofill/helper/server.py pair`, paste the token into the extension popup.
4. AI drafts (optional): store a key in the macOS Keychain. It reads stdin and never echoes.

   ```sh
   python3 job-autofill/helper/server.py set-key anthropic   # or: set-key openai
   ```

   Then pick the provider and model in the popup. Every AI draft stays yellow for your review.

Data lives in `JOB_AUTOFILL_HOME` (default `~/.config/job-autofill/`): config, manual profile fields, pairing token, answer cache, run log. Nothing personal is written in the repo.

## Run at login

```sh
cp job-autofill/helper/launchd/com.cloudtransition.job-autofill.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.cloudtransition.job-autofill.plist
```

Log: `~/.config/job-autofill/helper.log`. Stop: `launchctl bootout gui/$(id -u)/com.cloudtransition.job-autofill`. The plist points at this repo's path on the USB volume; edit `WorkingDirectory` if the repo moves.

## Tests

```sh
cd job-autofill && npm install && npm test && npm run check
```

## Troubleshooting

- **Helper offline**: filling still works from the profile and resume cached at the last sync; AI drafts show as unavailable and stay yellow. Start the helper and sync again.
- **Read requests look like POSTs**: Chrome omits the `Origin` header on GET fetches from extension pages and service workers, so the extension sends reads as `POST` with `X-HTTP-Method-Override: GET`. The helper requires `Origin: chrome-extension://…` on every request.
- **Popup shows "Not paired"**: the token is missing or was rejected. Run `server.py pair` and paste the token.
- **Port 8766 in use**: free it; the extension expects the helper on `127.0.0.1:8766`.
