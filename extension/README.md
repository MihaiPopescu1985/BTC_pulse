# Simple Runner

A minimal VS Code extension that shows configurable buttons in a tree view and runs script text from workspace-relative directories.

## Suggested Names

- Extension name: `Workspace Runner`
- Workspace config file: `simple-runner.yml`

The implementation currently keeps the extension id as `simple-runner` and reads `simple-runner.yml` from the workspace root.

## How It Works

- The extension adds a `Simple Runner` view in the Explorer side bar.
- It reads button definitions from `simple-runner.yml` in the first workspace folder.
- Each valid button entry appears as a clickable item.
- Each button has a `script` value.
- `script` can be either a single string or an array of strings.
- For multi-line scripts, YAML block style with `|` is the most readable option.
- When you run a button, the extension writes the configured script to a temporary file and executes that file as a standalone script.
- If the script starts with a shebang like `#!/bin/bash`, that shebang is honored.
- If the script has no shebang, the extension runs it with `/bin/bash` on Unix-like systems.
- The terminal working directory is set to the configured workspace-relative folder.
- Terminal output is visible live in VS Code.
- When `simple-runner.yml` changes, the tree view refreshes automatically.

## Configuration

Create `simple-runner.yml` in the workspace root.

Top-level format:

```yaml
buttons:
  - id: build
    label: Run build
    cwd: scripts
    script: npm run build
```

Readable multi-line example:

```yaml
buttons:
  - id: daily-reading
    label: Generate daily reading
    cwd: statistics
    script: |
      #!/bin/bash
      # Remove the old generated file to start clean
      rm -f daily_reading.txt

      echo "Press ENTER to continue."
      read

      while true; do
          read -r -p "Enter start date (yyyy-MM-DD): " start
          [[ $start =~ ^([0-9]{4})-(0[1-9]|1[0-2])-([0-2][0-9]|3[0-1])$ ]] && break
          echo "Only digits allowed."
      done

      while true; do
          read -r -p "Enter end date (yyyy-MM-DD): " end
          [[ $end =~ ^([0-9]{4})-(0[1-9]|1[0-2])-([0-2][0-9]|3[0-1])$ ]] && break
          echo "Only digits allowed."
      done

      source ../.venv/bin/activate

      python src/util/print_features_range.py \
        $start \
        $end \
        --path out/btc/features.json >> daily_reading.txt

      python src/util/print_features_range.py \
        $start \
        $end \
        --path out/btc/onchain_features.json >> daily_reading.txt

      python src/util/safe_touch_probabilities.py \
        --price-json data/daily_price.json \
        --features-json out/btc/features.json \
        --date $end \
        --days 10 \
        --sims 20000 >> daily_reading.txt
```

The extension also accepts this nested shape if you prefer to keep the old namespace idea:

```yaml
simpleRunner:
  buttons:
    - id: build
      label: Run build
      cwd: scripts
      script: npm run build
```

Each button supports:

- `id`: stable identifier
- `label`: text shown in the tree view
- `cwd`: workspace-relative directory where the script runs
- `script`: either one command as a string, a YAML block string with `|`, or a list of lines

## Notes

- If no workspace is open, the extension shows an error message.
- If `simple-runner.yml` is missing, the view shows a configuration message.
- If the YAML file is invalid, the view shows a configuration message.
- If the configured `cwd` does not exist, the extension shows an error message when you run a button.
- Entries missing `cwd` or `script` are ignored so a bad item does not break the whole view.
- If `label` is missing, the extension falls back to `id`.
- On Unix-like systems, YAML block scripts are executed as temporary standalone script files.
- If you want a specific interpreter, start the script with a shebang such as `#!/bin/bash` or `#!/usr/bin/env python3`.

## Run And Debug

1. Open `/home/mihai/Documents/BTC_pulse/extension` in VS Code.
2. Run `npm install`.
3. Run `npm run compile` once, or let the watch task handle builds.
4. Press `F5` to launch an Extension Development Host.
5. In the new window, open a normal single-root workspace.
6. Create `simple-runner.yml` in that workspace root.
7. Use the `Simple Runner` view in Explorer.

## Files

- `package.json`: extension manifest and dependency list
- `src/extension.ts`: tree view provider, YAML config loading, and run command implementation
- `tsconfig.json`: TypeScript compiler settings
- `.vscode/launch.json`: debug configuration
- `.vscode/tasks.json`: build and watch tasks
