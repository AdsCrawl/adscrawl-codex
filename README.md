# AdsCrawl for Codex

AdsCrawl adds browser-rendered page reading and screenshots to Codex. The plugin bundles an `adscrawl-browser` skill and a Python 3.9+ command that uses only the standard library. It calls the AdsCrawl API using your `ADSCRAWL_API_KEY` and does not bundle credentials.

## Features

- Render a URL as Markdown, HTML, or structured article JSON.
- Capture a full-page or viewport PNG screenshot.
- Select a managed country route and navigation wait strategy.
- Use AdsCrawl CDP sessions for interactive browser work through your project's browser automation library.

## Requirements

Create an [AdsCrawl account](https://app.adscrawl.net/register/) and set `ADSCRAWL_API_KEY` in the environment where Codex runs. Requests can consume AdsCrawl credits. Python 3.9+ is required for the bundled command.

## Install from the repository marketplace

Once this repository is published on GitHub:

```bash
codex plugin marketplace add AdsCrawl/adscrawl-codex
codex plugin add adscrawl@adscrawl
```

Start a new Codex task after installation so the bundled skill is loaded. You can also add the local checkout as a marketplace while developing:

```bash
codex plugin marketplace add /path/to/adscrawl-codex
codex plugin add adscrawl@adscrawl
```

## Direct command

The skill invokes `plugins/adscrawl/scripts/adscrawl.py`. You can run it directly:

```bash
python3 plugins/adscrawl/scripts/adscrawl.py render \
  --url 'https://example.com/' --format markdown --output page.md

python3 plugins/adscrawl/scripts/adscrawl.py screenshot \
  --url 'https://example.com/' --output page.png
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
