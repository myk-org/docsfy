# Browse and Download Docs

You want to get from a finished generation to something you can read, share, or archive. The fastest path is to open the latest ready docs site in your browser, then download the same output as a tarball or a local extracted copy when you need it offline or in another tool.

## Prerequisites

- A running docsfy server.
- A signed-in docsfy account with access to the project.
- At least one ready generation for that project.
- The `docsfy` CLI if you want local downloads or extraction.

## Quick Example

```text
https://docsfy.example.com/docs/my-project/
```

```bash
docsfy download my-project --output ./my-project-docs --flatten
```

Open the URL to read the newest ready docs you can access for `my-project`. Run the command to save a local copy with `index.html`, `llms.txt`, and `llms-full.txt` directly in `./my-project-docs/`.

## Step-by-Step

1. Open the latest ready docs site.

```text
https://docsfy.example.com/docs/my-project/
```

Use this when you want the newest ready variant without caring which branch, provider, or model produced it. On the home page, use the page cards to jump into a section, or use the sidebar once you are inside a page.

> **Note:** For shared projects, the latest route follows the newest ready variant you are allowed to access.

2. Open one exact variant when you do not want the site to move to a newer run.

```text
https://docsfy.example.com/docs/my-project/main/claude/<model-id>/
```

Use the variant-specific URL when you need a fixed branch and model. This is the safest choice for release docs, comparisons, or reproducible links.

| If you want | Open this path |
| --- | --- |
| newest ready docs you can access | `/docs/my-project/` |
| one exact variant | `/docs/my-project/<branch>/<provider>/<model>/` |

If you need help finding the exact branch, provider, model, or generation ID, see [Manage Projects and Variants](manage-projects-and-variants.html) for details.

3. Download a tarball.

```bash
docsfy download my-project
```

```bash
docsfy download my-project --branch main --provider claude --model <model-id>
```

The first command downloads the newest ready variant as `my-project-docs.tar.gz` in your current directory. The second command downloads one exact variant instead.

> **Tip:** For more day-to-day command patterns, see [Run Common CLI Workflows](common-workflow-recipes.html).

4. Extract a local copy instead of keeping the tarball.

```bash
docsfy download my-project --output ./my-project-docs
```

```bash
docsfy download my-project --output ./my-project-docs --flatten
```

Use `--output` when you want a browsable directory right away. Add `--flatten` when you want the site files directly in the target directory instead of one nested top-level folder.

| Command | Result | Where to open `index.html` |
| --- | --- | --- |
| `docsfy download my-project --output ./my-project-docs` | extracted copy, keeps the tarball’s top-level folder | inside the extracted project folder |
| `docsfy download my-project --output ./my-project-docs --flatten` | extracted copy, flattened into the target directory | `./my-project-docs/index.html` |

> **Warning:** When you use `--output`, docsfy replaces the contents of the target directory after a successful download and extract. Use a dedicated directory if you need to keep other files.

5. Find the AI-readable outputs.

```text
https://docsfy.example.com/docs/my-project/llms.txt
https://docsfy.example.com/docs/my-project/llms-full.txt
```

```text
https://docsfy.example.com/docs/my-project/main/claude/<model-id>/llms.txt
https://docsfy.example.com/docs/my-project/main/claude/<model-id>/llms-full.txt
```

Use `llms.txt` when you want a structured index of the rendered pages. Use `llms-full.txt` when you want the full documentation in one file. If you downloaded with `--flatten`, both files sit at the root of your output directory.

`llms.txt` links to per-page Markdown files, so you can also fetch one page at a time when you do not need the full site.

## Advanced Usage

- Use a generation ID when you want the CLI to resolve the exact variant for you:

```bash
docsfy download 123e4567-e89b-12d3-a456-426614174000 --output ./my-project-docs --flatten
```

- Encode branch names in variant URLs when the branch contains `/` or `~`:
  - `release/1.0` becomes `release~2F1.0`
  - `feature~beta` becomes `feature~7Ebeta`

```text
https://docsfy.example.com/docs/my-project/release~2F1.0/claude/<model-id>/
```

- If you are an admin and the same variant exists under more than one owner, disambiguate CLI downloads with `--owner`:

```bash
docsfy download my-project --branch main --provider claude --model <model-id> --owner alice
```

- If you need exact endpoint forms for automation, see [HTTP API and WebSocket Reference](http-api-and-websocket-reference.html).

## Troubleshooting

- If a docs URL sends you to `/login`, sign in first. The docs routes require authentication.
- If `docsfy download` returns `No ready variant` or the browser shows `No docs available`, wait for a successful generation or start a new one. See [Track Generation Progress](track-generation-progress.html) and [Generate Documentation](generate-documentation.html) for details.
- If a variant-specific URL returns `File not found`, re-check the branch, provider, and model. Branches with `/` must use the encoded form in the URL.
- If `docsfy download ... --flatten` fails with `--flatten requires --output`, add an output directory and rerun the command.
- If you expected shared docs but get `Not found`, ask an admin to confirm that access was granted. See [Manage Users and Access](manage-users-and-access.html) for the access model.
- If you cannot find `index.html`, `llms.txt`, or `llms-full.txt` after extraction, look inside the nested project folder or rerun with `--flatten`.

## Related Pages

- [Track Generation Progress](track-generation-progress.html)
- [Manage Projects and Variants](manage-projects-and-variants.html)
- [Run Common CLI Workflows](common-workflow-recipes.html)
- [HTTP API and WebSocket Reference](http-api-and-websocket-reference.html)
- [Generate Documentation](generate-documentation.html)