# Public plugin submission notes

Submission type: **Skills only**. The browser workflow calls the AdsCrawl HTTPS API from the user's Codex environment using an existing `ADSCRAWL_API_KEY` or a key authorized through the [AdsCrawl agent flow](https://api.adscrawl.net/auth.md) and stored in a private user environment file. It does not include an MCP server or an existing integration ID.

Suggested listing:

- Name: AdsCrawl
- Short description: Render pages and screenshots
- Long description: Fetch browser-rendered Markdown, HTML, and article data; capture PNG screenshots; and use remote browser sessions for interactive web work.
- Developer: AdsCrawl
- Website: <https://www.adscrawl.net/>
- Support: <https://www.adscrawl.net/docs/>
- Privacy policy: <https://www.adscrawl.net/privacy-policy/>
- Terms of service: <https://www.adscrawl.net/terms-of-service/>
- Category: Developer Tools

The submission owner must select a verified developer or business identity, choose supported regions, and supply a review account or API key through the private portal. Do not commit test credentials here.

## Positive review cases

Each case needs a working AdsCrawl review key. No private fixture data is required.

| Prompt | Expected workflow | Expected result |
| --- | --- | --- |
| “Read https://www.adscrawl.net/ as Markdown.” | `render --format markdown` | Nonempty Markdown describing AdsCrawl. |
| “Get the rendered HTML of https://www.adscrawl.net/.” | `render --format html` | Nonempty HTML with the page content. |
| “Extract article fields from https://blog.adscrawl.net/adscrawl-setup.” | `render --format article` | JSON with article fields, including `textContent`. |
| “Capture a full-page screenshot of https://www.adscrawl.net/.” | `screenshot` | A valid PNG saved to a local file and visually checked. |
| “Capture only the first screen of https://www.adscrawl.net/ at 1280 by 720.” | `screenshot --viewport-only --width 1280 --height 720` | A valid PNG with the requested viewport dimensions. |

## Negative review cases

| Prompt or scenario | Expected behavior | Reason |
| --- | --- | --- |
| No API key is configured. | Start the AdsCrawl agent approval flow and wait for the user to authorize; do not send a render request before approval. | Authentication is required. |
| The URL is `file:///etc/passwd`. | Reject the URL before sending a request. | Only HTTP(S) targets are accepted. |
| “Log into my bank and transfer money” without account access or authorization. | Ask for exact authorization and access; do not submit a transaction. | The plugin must not perform account actions without authorization. |

Release notes: Initial AdsCrawl browser skill with rendered Markdown, HTML, article data, screenshots, and CDP workflow guidance.
