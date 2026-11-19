# Image descriptions

Plain-text, searchable descriptions for workspace-owned images, plus the exact generation prompt when one was saved. No database, service or dependency: `tools/arms/image_descriptions.py` (stdlib) and Markdown sidecars. Coverage list: [resources/image-coverage.md](../../resources/image-coverage.md).

## Commands

```sh
python3 tools/arms/image_descriptions.py inventory            # rewrite resources/image-coverage.md (metadata + local hash only)
python3 tools/arms/image_descriptions.py describe             # dry run: images with no sidecar
python3 tools/arms/image_descriptions.py describe --run       # caption them with Claude Haiku via the Claude CLI
python3 tools/arms/image_descriptions.py register path/to/new.png \
    --prompt-file prompt.txt --model "<generator model>" [--tool "<tool>"]
```

`register` is for NEW images: save the exact prompt to a file (or `--prompt-file -` for stdin) at generation time. The file is read as UTF-8 bytes with no stripping or newline translation. The sidecar stores it in a fenced `## Original prompt` block (fence longer than any backtick run in the prompt), so the exact prompt is the text between the opening and closing fence lines minus the one separator newline before the closing fence. `Prompt SHA-256` is the hash of the original UTF-8 prompt text. The same call always adds a Haiku caption, so a registered sidecar is never left without a description. `--model` is the model that made the image, never the captioner.

## Sidecar rules

- Location and name: `<image-filename>.md` beside the image (`cover.png.md`, `la chispa.avif.md`). An older `<stem>.md` that links to the image (`resources/1779037629264.md`) is kept and honoured.
- Never overwritten: the helper creates sidecars exclusively and refuses if one exists. Fix a wrong caption by editing the file by hand.
- Fields (one `- Label: value` line each): `Original prompt` (`unknown` unless recorded), `Generator model`, `Generator tool`, `Prompt recorded`, `Prompt SHA-256`, `Caption model`, `Caption date`, `Caption route`, `Caption status`, `Image SHA-256`. Then the description, `Visible text:` and `Uncertainty:`. A caption is never a prompt; creator, ownership and identity are not inferred.
- `Caption model` is read from the Claude CLI's reported `modelUsage`, not the requested alias. The helper aborts and writes nothing if the billed model does not match the request. This machine's CLI goes through a local proxy (host recorded in `Caption route`); the alias `haiku` resolved to `claude-haiku-5-5` on 2026-11-02. Re-verify if routing or aliases change.
- Images in `dashboard-app/static/` get sidecars beside them, so the dashboard's `/static` mount serves those `.md` files too. They hold only an icon description.

## Scope

In scope: images the workspace authored. Excluded and counted, never decoded or uploaded: dot directories, dependency/build output, third-party projects (`projects/rendercv`, `andrej-karpathy-skills`), saved web pages (`*_files`), `College Planning` (personal records), directories or image filenames matching `private|employer|secret|credential` (this covers `IT Mgmt/Employer-IT-Playbook-Private/`), the standalone nested repo `r8s11/` (ownership not established), and symlinks (the file or any parent directory). Nested git alone does not exclude a folder. `projects/ReactNative/Mytvapp/assets/images` is not excluded as a folder: only files whose SHA-256 equals one of the 10 recorded originals from `expo-template-default@54.0.63` are skipped (hashes live in `TEMPLATE_HASHES`), so a new or edited asset there stays in scope. Provenance was established by a local hash comparison, the only place excluded files are byte-read, and only for those template-named files. The rules and reasons live in `dir_exclusion`/`file_exclusion`/`EXPLICIT` in the helper and are printed in the coverage list. Cost: roughly 0.0003 to 0.001 USD per image at list rates, capped by `--budget-per-call` (default 0.1).

Tests: `python3 -m unittest discover -s tools/arms -p 'test_image_descriptions.py'`.
