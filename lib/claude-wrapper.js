#!/usr/bin/env node

/**
 * Claude Code LLMプール・フェイルオーバーラッパー
 * 
 * このラッパーはClaude Code CLIを起動し、API呼び出しをインターセプトして
 * LLMプールのフェイルオーバー機能を適用します。
 */

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

// モジュールパスの解決
const libPath = path.join(os.homedir(), '.claude', 'lib');
const settingsPath = path.join(os.homedir(), '.claude', 'settings.json');

// 依存モジュールのロード
const LLMPoolManager = require(path.join(libPath, 'llm-pool-manager'));
const LLMFallbackClient = require(path.join(libPath, 'llm-fallback-client'));
const SettingsValidator = require(path.join(libPath, 'settings-validator'));
const EnvLoader = require(path.join(libPath, 'env-loader'));

/**
 * 設定をロード
 */
function loadSettings() {
  try {
    const content = fs.readFileSync(settingsPath, 'utf8');
    return JSON.parse(content);
  } catch (error) {
    console.error('[Wrapper] Failed to load settings:', error.message);
    process.exit(1);
  }
}

/**
 * 設定をバリデート
 */
function validateSettings(settings) {
  const result = SettingsValidator.validateAll(settings);
  
  if (!result.valid) {
    console.error('\n=== Settings Validation Errors ===');
    result.errors.forEach(err => console.error(`  ✗ ${err}`));
    console.error('=====================================\n');
    process.exit(1);
  }

  if (result.warnings.length > 0) {
    console.warn('\n=== Settings Validation Warnings ===');
    result.warnings.forEach(warn => console.warn(`  ⚠️  ${warn}`));
    console.error('======================================\n');
  }

  return result.valid;
}

/**
 * 現在のプロバイダー設定を環境変数に設定
 */
function applyProviderSettings(provider) {
  if (!provider) return;

  console.log(`[Wrapper] Applying provider: ${provider.name} (Priority: ${provider.priority}, Cost: $${provider.costPer1kTokens}/1K tokens)`);
  
  // .envからAPIキーを取得（優先）
  const providerKeys = EnvLoader.getLLMProviderKeys();
  let apiKeyValue = null;

  if (provider.apiKey && !provider.apiKey.startsWith('sk-')) {
    // 環境変数名の場合（例: MINIMAX_API_KEY）
    apiKeyValue = providerKeys[provider.apiKey] || process.env[provider.apiKey] || provider.apiKey;
  } else if (provider.apiKey) {
    // 直接キー値の場合
    apiKeyValue = provider.apiKey;
  }

  if (apiKeyValue) {
    process.env.ANTHROPIC_AUTH_TOKEN = apiKeyValue;
  }

  if (provider.baseURL) {
    process.env.ANTHROPIC_BASE_URL = provider.baseURL;
  }

  if (provider.model) {
    process.env.ANTHROPIC_DEFAULT_SONNET_MODEL = provider.model;
    process.env.ANTHROPIC_DEFAULT_OPUS_MODEL = provider.model;
    process.env.ANTHROPIC_DEFAULT_HAIKU_MODEL = provider.model;
  }
}

/**
 * Claude Codeプロセスを起動
 */
function spawnClaude() {
  const settings = loadSettings();
  validateSettings(settings);

  // 設定の確認・表示
  console.log('\n=== Claude Code LLM Pool Settings ===');

  if (settings.llmPool?.enabled) {
    console.log(`✓ LLM Pool: Enabled`);
    console.log(`  Cooldown Period: ${settings.llmPool.cooldownPeriod / 1000}s`);
    console.log(`  Active Providers: ${settings.llmPool.providers.length}`);
    console.log('\n  Providers:');
    settings.llmPool.providers.forEach(p => {
      const statusIcon = p.active ? '✓' : '✗';
      console.log(`    ${statusIcon} ${p.name.padEnd(20)} | Priority: ${p.priority} | Cost: $${p.costPer1kTokens}/1K`);
    });
  } else {
    console.log(`✗ LLM Pool: Disabled`);
  }

  console.log('========================================\n');

  // .envファイルからAPIキーをロード
  if (EnvLoader.shouldLoadEnvFromArgs()) {
    console.log('[Wrapper] Loading .env file...');
    const providerKeys = EnvLoader.loadEnv();

    if (Object.keys(providerKeys).length > 0) {
      console.log('[Wrapper] ✓ API keys loaded from .env');
    }
  }

  // .envファイルからAPIキーをロード
  if (EnvLoader.shouldLoadEnvFromArgs()) {
    console.log('[Wrapper] Loading .env file...');
    const providerKeys = EnvLoader.loadEnv();
    
    if (Object.keys(providerKeys).length > 0) {
      console.log('[Wrapper] ✓ API keys loaded from .env');
    }
  }

  // LLMプールが無効の場合、直接起動
  if (!settings.llmPool?.enabled) {
    console.log('[Wrapper] LLM Pool is disabled, starting Claude Code directly...');
    return spawnDirect(settings);
  }

  console.log('[Wrapper] LLM Pool is enabled, initializing...');
  console.log(`[Wrapper] Cooldown period: ${settings.llmPool.cooldownPeriod / 1000}s`);
  console.log(`[Wrapper] Active providers: ${settings.llmPool.providers.length}`);
  console.log('');

  // LLMプールマネージャーを初期化
  const poolManager = new LLMPoolManager(settings);
  
  // 現在のアクティブプロバイダーを取得・適用
  const currentProvider = poolManager.getNextAvailableProvider();
  if (currentProvider) {
    applyProviderSettings(currentProvider);
  }

  // Claude Codeを起動
  return spawnDirect(settings);
}

/**
 * Claude Codeを直接起動
 */
function spawnDirect(settings) {
  const claudeExe = process.platform === 'win32' ? 'claude.exe' : 'claude';

  // Claude Codeのパスを検索（Program Files、LOCALAPPDATA、カレントディレクトリなど）
  const claudePath = findClaudeExecutable() || claudeExe;

  // settingsのenvをプロセス環境変数にマージ
  if (settings.env) {
    Object.assign(process.env, settings.env);
  }

  console.log('[Wrapper] Starting Claude Code...\n');
  console.log(`[Wrapper] Executable: ${claudePath}`);
  console.log('='.repeat(50));

  const claudeProcess = spawn(claudePath, process.argv.slice(2), {
    stdio: 'inherit',
    env: process.env
  });

  claudeProcess.on('error', (error) => {
    console.error('[Wrapper] Failed to start Claude Code:', error);
    process.exit(1);
  });

  claudeProcess.on('exit', (code) => {
    console.log(`\n[Wrapper] Claude Code exited with code: ${code}`);
    process.exit(code);
  });

  // シグナルハンドリング
  process.on('SIGINT', () => {
    claudeProcess.kill('SIGINT');
  });

  process.on('SIGTERM', () => {
    claudeProcess.kill('SIGTERM');
  });
}

/**
 * Claude Code実行可能ファイルを検索
 */
function findClaudeExecutable() {
  const possiblePaths = [
    path.join(process.env.ProgramFiles || 'C:\\Program Files', 'Claude', 'claude.exe'),
    path.join(process.env.LOCALAPPDATA || '', 'Claude', 'claude.exe'),
    path.join(os.homedir(), 'AppData', 'Local', 'Claude', 'claude.exe'),
    path.join(process.env.USERPROFILE || os.homedir(), 'Claude', 'claude.exe'),
    path.join(os.homedir(), 'scoop', 'apps', 'Claude', 'claude.exe')
  ];

  for (const claudePath of possiblePaths) {
    if (fs.existsSync(claudePath)) {
      console.log(`[Wrapper] Found Claude Code at: ${claudePath}`);
      return claudePath;
    }
  }

  return null;
}

/**
 * コマンドライン引数の解析
 */
function parseArgs() {
  const args = process.argv.slice(2);
  
  // ヘルプオプション
  if (args.includes('--help') || args.includes('-h')) {
    console.log(`
Claude Code LLM Pool Wrapper

Usage:
  node ~/.claude/lib/claude-wrapper.js [claude-options]

Options:
  --help, -h      Show this help message
  --status         Show current LLM pool status
  --test           Run LLM pool tests

Examples:
  node ~/.claude/lib/claude-wrapper.js
  node ~/.claude/lib/claude-wrapper.js --help
  node ~/.claude/lib/claude-wrapper.js --status
`);
    process.exit(0);
  }

  // ステータスオプション
  if (args.includes('--status')) {
    showStatus();
    process.exit(0);
  }

  // テストオプション
  if (args.includes('--test')) {
    runTests();
    process.exit(0);
  }
}

/**
 * LLMプールのステータスを表示
 */
function showStatus() {
  const settings = loadSettings();
  
  if (!settings.llmPool?.enabled) {
    console.log('LLM Pool: Disabled');
    return;
  }

  const manager = new LLMPoolManager(settings);
  const stats = manager.getStats();
  const providers = manager.getProviderStatus();

  console.log('\n=== LLM Pool Status ===');
  console.log(`Enabled: ${stats.enabled ? 'Yes' : 'No'}`);
  console.log(`Cooldown Period: ${stats.cooldownPeriod / 1000}s`);
  console.log(`Active Providers: ${stats.activeProviders}/${stats.totalProviders}`);
  console.log(`Total Fallbacks: ${stats.totalFallbacks}`);
  console.log(`Reset Attempts: ${stats.resetAttempts}`);
  
  console.log('\n--- Providers ---');
  providers.forEach(p => {
    const statusIcon = p.status === 'available' ? '✓' : p.status === 'cooldown' ? '⏳' : '✗';
    console.log(`${statusIcon} ${p.name.padEnd(20)} | Priority: ${p.priority} | Cost: $${p.costPer1kTokens}/1K | Fallbacks: ${p.fallbackCount}`);
  });
  console.log('=====================\n');
}

/**
 * LLMプールのテストを実行
 */
function runTests() {
  console.log('Running LLM Pool tests...\n');
  
  try {
    const tests = require(path.join(libPath, 'test-llm-pool'));
    tests.runAllTests();
  } catch (error) {
    console.error('Failed to run tests:', error.message);
    process.exit(1);
  }
}

/**
 * メイン関数
 */
function main() {
  parseArgs();
  spawnClaude();
}

// アプリケーション起動
if (require.main === module) {
  main();
}

module.exports = {
  spawnClaude,
  showStatus,
  runTests
};
