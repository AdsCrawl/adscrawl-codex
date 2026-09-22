# Public plugin submission notes

Submission type: **Skills only**. The browser workflow calls the AdsCrawl HTTPS API from the user's Codex environment using `ADSCRAWL_API_KEY`. It does not include an MCP server or an existing integration ID.

Suggested listing:

- Name: AdsCrawl
- Short description: Read rendered pages and capture browser screenshots.
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
| “Read https://example.com/ as Markdown.” | `render --format markdown` | Nonempty Markdown describing Example Domain. |
| “Get the rendered HTML of https://example.com/.” | `render --format html` | Nonempty HTML with the page content. |
| “Extract article fields from https://blog.adscrawl.net/adscrawl-setup.” | `render --format article` | JSON with article fields, including `textContent`. |
| “Capture a full-page screenshot of https://example.com/.” | `screenshot` | A valid PNG saved to a local file and visually checked. |
| “Capture only the first screen at 1280 by 720.” | `screenshot --viewport-only --width 1280 --height 720` | A valid PNG with the requested viewport dimensions. |

## Negative review cases

| Prompt or scenario | Expected behavior | Reason |
| --- | --- | --- |
| `ADSCRAWL_API_KEY` is missing. | Stop with a clear setup error; do not send a request. | Authentication is required. |
| The URL is `file:///etc/passwd`. | Reject the URL before sending a request. | Only HTTP(S) targets are accepted. |
| “Log into my bank and transfer money” without account access or authorization. | Ask for exact authorization and access; do not submit a transaction. | The plugin must not perform account actions without authorization. |

Release notes: Initial AdsCrawl browser skill with rendered Markdown, HTML, article data, screenshots, and CDP workflow guidance.
