import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { parse } from "yaml";

const CONFIG_FILE_NAME = "simple-runner.yml";

type ScriptSetting = string | string[];

interface ButtonConfig {
  id: string;
  label: string;
  cwd: string;
  script: string;
}

class ButtonTreeItem extends vscode.TreeItem {
  constructor(public readonly button: ButtonConfig) {
    super(button.label, vscode.TreeItemCollapsibleState.None);

    this.id = button.id;
    this.description = button.cwd;
    this.tooltip = new vscode.MarkdownString(
      `**${button.label}**\n\nDirectory: \`${button.cwd}\`\n\nScript:\n\n\`\`\`sh\n${button.script}\n\`\`\``
    );
    this.iconPath = new vscode.ThemeIcon("play");
    this.command = {
      command: "simpleRunner.runButton",
      title: "Run button",
      arguments: [button]
    };
  }
}

class MessageTreeItem extends vscode.TreeItem {
  constructor(label: string, description?: string) {
    super(label, vscode.TreeItemCollapsibleState.None);

    this.description = description;
    this.iconPath = new vscode.ThemeIcon("info");
  }
}

class ButtonsProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
  private readonly onDidChangeTreeDataEmitter = new vscode.EventEmitter<void>();
  readonly onDidChangeTreeData = this.onDidChangeTreeDataEmitter.event;

  refresh(): void {
    this.onDidChangeTreeDataEmitter.fire();
  }

  getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: vscode.TreeItem): vscode.TreeItem[] {
    if (element) {
      return [];
    }

    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];

    if (!workspaceFolder) {
      return [
        new MessageTreeItem(
          "No workspace open",
          "Open a workspace folder to use Simple Runner"
        )
      ];
    }

    const configState = readButtonsFromWorkspaceConfig(workspaceFolder.uri.fsPath);

    if (configState.errorMessage) {
      return [
        new MessageTreeItem(
          "Configuration problem",
          configState.errorMessage
        )
      ];
    }

    if (configState.buttons.length === 0) {
      return [
        new MessageTreeItem(
          "No valid buttons configured",
          `Edit ${CONFIG_FILE_NAME} in the workspace root`
        )
      ];
    }

    return configState.buttons.map((button) => new ButtonTreeItem(button));
  }
}

export function activate(context: vscode.ExtensionContext): void {
  const provider = new ButtonsProvider();

  const treeView = vscode.window.createTreeView("simpleRunnerView", {
    treeDataProvider: provider,
    showCollapseAll: false
  });

  const runCommand = vscode.commands.registerCommand(
    "simpleRunner.runButton",
    async (button: ButtonConfig) => {
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];

      if (!workspaceFolder) {
        vscode.window.showErrorMessage(
          "Simple Runner: open a workspace folder before running a button."
        );
        return;
      }

      if (!button?.cwd || !button?.script) {
        vscode.window.showErrorMessage(
          "Simple Runner: the selected button is missing cwd or script."
        );
        return;
      }

      // Resolve the configured directory relative to the first workspace folder.
      const targetDirectory = path.resolve(workspaceFolder.uri.fsPath, button.cwd);

      if (!directoryExists(targetDirectory)) {
        vscode.window.showErrorMessage(
          `Simple Runner: configured directory does not exist: ${button.cwd}`
        );
        return;
      }

      // A terminal is the simplest way to show live command output inside VS Code.
      // The normalized script text is sent as-is, so it can be one command or many lines.
      const terminal = vscode.window.createTerminal({
        name: `Simple Runner: ${button.label}`,
        cwd: targetDirectory
      });

      terminal.show(true);
      terminal.sendText(button.script, true);
    }
  );

  const workspaceWatcher = vscode.workspace.onDidChangeWorkspaceFolders(() => {
    provider.refresh();
  });

  context.subscriptions.push(treeView, runCommand, workspaceWatcher);

  registerConfigWatchers(context, provider);
}

export function deactivate(): void {}

function registerConfigWatchers(
  context: vscode.ExtensionContext,
  provider: ButtonsProvider
): void {
  for (const folder of vscode.workspace.workspaceFolders ?? []) {
    const pattern = new vscode.RelativePattern(folder, CONFIG_FILE_NAME);
    const watcher = vscode.workspace.createFileSystemWatcher(pattern);

    const refresh = () => provider.refresh();
    watcher.onDidCreate(refresh);
    watcher.onDidChange(refresh);
    watcher.onDidDelete(refresh);

    context.subscriptions.push(watcher);
  }
}

function readButtonsFromWorkspaceConfig(workspaceRoot: string): {
  buttons: ButtonConfig[];
  errorMessage?: string;
} {
  const configPath = path.join(workspaceRoot, CONFIG_FILE_NAME);

  if (!fs.existsSync(configPath)) {
    return {
      buttons: [],
      errorMessage: `Missing ${CONFIG_FILE_NAME} in the workspace root`
    };
  }

  let parsed: unknown;

  try {
    parsed = parse(fs.readFileSync(configPath, "utf8"));
  } catch {
    return {
      buttons: [],
      errorMessage: `Could not parse ${CONFIG_FILE_NAME}`
    };
  }

  const rawButtons = readButtonsValue(parsed);

  if (!Array.isArray(rawButtons)) {
    return {
      buttons: [],
      errorMessage: `Expected a buttons list in ${CONFIG_FILE_NAME}`
    };
  }

  return {
    buttons: rawButtons
      .map((item, index) => normalizeButton(item, index))
      .filter((item): item is ButtonConfig => item !== undefined)
  };
}

function readButtonsValue(parsed: unknown): unknown {
  if (!parsed || typeof parsed !== "object") {
    return undefined;
  }

  const root = parsed as Record<string, unknown>;

  if (Array.isArray(root.buttons)) {
    return root.buttons;
  }

  if (root.simpleRunner && typeof root.simpleRunner === "object") {
    const nested = root.simpleRunner as Record<string, unknown>;
    return nested.buttons;
  }

  return undefined;
}

function normalizeButton(value: unknown, index: number): ButtonConfig | undefined {
  if (!value || typeof value !== "object") {
    return undefined;
  }

  const item = value as Record<string, unknown>;
  const id = readNonEmptyString(item.id) ?? `button-${index + 1}`;
  const label = readNonEmptyString(item.label) ?? id;
  const cwd = readNonEmptyString(item.cwd);
  const script = normalizeScript(item.script);

  // Skip invalid entries so a bad config item does not break the whole view.
  if (!cwd || !script) {
    return undefined;
  }

  return { id, label, cwd, script };
}

function normalizeScript(value: ScriptSetting | unknown): string | undefined {
  if (typeof value === "string") {
    return readNonEmptyString(value);
  }

  if (!Array.isArray(value)) {
    return undefined;
  }

  const lines = value
    .map((line) => (typeof line === "string" ? line : undefined))
    .filter((line): line is string => line !== undefined);

  if (lines.length !== value.length) {
    return undefined;
  }

  const script = lines.join("\n").trim();
  return script.length > 0 ? script : undefined;
}

function readNonEmptyString(value: unknown): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function directoryExists(targetPath: string): boolean {
  try {
    return fs.statSync(targetPath).isDirectory();
  } catch {
    return false;
  }
}
