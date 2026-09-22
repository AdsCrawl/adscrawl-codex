# AdsCrawl for Codex

AdsCrawl adds browser-rendered page reading and screenshots to Codex. The plugin bundles an `adscrawl-browser` skill and a Python 3.9+ command that uses only the standard library. It calls the AdsCrawl API using your `ADSCRAWL_API_KEY` and does not bundle credentials.

## Features

- Render a URL as Markdown, HTML, or structured article JSON.
- Capture a full-page or viewport PNG screenshot.
- Select a managed country route and navigation wait strategy.
- Use AdsCrawl CDP sessions for interactive browser work through your project's browser automation library.

## Requirements

Create an [AdsCrawl account](https://app.adscrawl.net/register/) or sign in when prompted. After installing the plugin, ask Codex to connect your AdsCrawl account, or run the auth command below. It opens a short-lived approval flow described in the [AdsCrawl agent authentication guide](https://api.adscrawl.net/auth.md). You approve an existing or new API key in your own browser; the plugin saves it privately at `~/.config/adscrawl/codex.env` with `0600` permissions. An existing `ADSCRAWL_API_KEY` environment variable is reused. Requests can consume AdsCrawl credits. Python 3.9+ is required for the bundled command.

## Install from the repository marketplace

Install the plugin from this public GitHub repository:

```bash
codex plugin marketplace add AdsCrawl/adscrawl-codex
codex plugin add adscrawl@adscrawl
```

Start a new Codex task after installation so the bundled skill is loaded. You can also add the local checkout as a marketplace while developing:

```bash
codex plugin marketplace add /path/to/adscrawl-codex
codex plugin add adscrawl@adscrawl
```

From a repository checkout, connect your account when first using the plugin. If you installed it from the marketplace without a checkout, ask Codex to connect AdsCrawl for you:

```bash
python3 plugins/adscrawl/scripts/adscrawl.py auth
```

The command asks for your account email and a project name, then prints a link for you to approve. It never asks for your password or prints the resulting API key.

## Direct command

The skill invokes `plugins/adscrawl/scripts/adscrawl.py`. You can run it directly:

```bash
python3 plugins/adscrawl/scripts/adscrawl.py render \
  --url 'https://www.adscrawl.net/' --format markdown --output page.md

python3 plugins/adscrawl/scripts/adscrawl.py screenshot \
  --url 'https://www.adscrawl.net/' --output page.png
```

Run `python3 plugins/adscrawl/scripts/adscrawl.py <command> --help` for the available options. API failures are not retried automatically.

## Development

```bash
python3 -m unittest discover -s tests -v
```

The tests use an in-process fake response and do not call AdsCrawl or consume credits. The Codex compatibility manifest is at `plugins/adscrawl/.codex-plugin/plugin.json`; the marketplace catalog is at `.agents/plugins/marketplace.json`.

## Public directory status

The Git marketplace makes the plugin installable from this repository. A listing in the universal ChatGPT/Codex Plugins Directory requires a separate [OpenAI submission and review](https://developers.openai.com/plugins/deploy/submission).

## License

MIT. See [LICENSE](./LICENSE).
