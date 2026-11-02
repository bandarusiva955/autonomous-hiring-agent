# AI Job Match Checker (Chrome extension)

One click on any job page shows how well your skills match, what is missing, and a roadmap to close the gap. A small chat box answers follow-up questions.

## Install for development

1. Start the app: `python app.py` (or `setup.ps1` on Windows) so it runs at `http://127.0.0.1:5000`.
2. Open `chrome://extensions`, turn on **Developer mode**, click **Load unpacked**, and choose this `extension` folder.
3. Pin the extension. Open the popup and click **Import from resume** (or type your skills).
4. Open any job posting, click the extension, then **Check this job**.

Tip: select just the job description text on the page first for a more precise result.

## What it sends, and where

Only to the server address in Settings (default: your own local app):
- the job page text (or your selection), when you click **Check this job**
- your skill list, and your chat messages
- your resume file, only when you click **Import from resume**; it is parsed and discarded, and only the skill list is saved in the extension

Nothing is sent in the background and no page is read until you click the button (`activeTab`).

## Using a deployed server

Open **Settings**, enter your server address (for example `https://your-app.example.com`), and approve the permission prompt. Use HTTPS for anything other than localhost.

## Publishing to the Chrome Web Store (later)

- Needs a one-time developer registration fee and a privacy policy page that matches the section above.
- Replace the default localhost address with your deployed HTTPS server and add it to `host_permissions`.
- Store review checks that requested permissions are the minimum needed, so keep `activeTab` rather than broad page access.
