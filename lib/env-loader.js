/**
 * 環境変数ローダー
 * .envファイルから環境変数を読み込みます
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

/**
 * .envファイルのパスを取得
 */
function getEnvPath() {
  return path.join(os.homedir(), '.claude', '.env');
}

/**
 * .envファイルを読み込み・パース
 * @param {string} filePath - .envファイルのパス
 * @returns {Object} パースされた環境変数
 */
function parseEnvFile(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    const envVars = {};
    
    // 行ごとにパース
    content.split('\n').forEach(line => {
      // 空行・コメント行をスキップ
      const trimmedLine = line.trim();
      if (!trimmedLine || trimmedLine.startsWith('#')) {
        return;
      }

      // KEY=VALUE 形式をパース
      const match = trimmedLine.match(/^([^=]+)=(.*)$/);
      if (match) {
        const key = match[1].trim();
        const value = match[2].trim();
        
        // クオーテーションを削除（"value" も 'value'）
        if (value.startsWith('"') && value.endsWith('"')) {
          envVars[key] = value.slice(1, -1);
        } else if (value.startsWith("'") && value.endsWith("'")) {
          envVars[key] = value.slice(1, -1);
        } else {
          envVars[key] = value;
        }
      }
    });

    return envVars;
  } catch (error) {
    if (error.code === 'ENOENT') {
      // .envファイルが存在しない場合、空のオブジェクトを返す
      console.warn('[EnvLoader] .env file not found, using only system environment variables');
      return {};
    }
    console.error('[EnvLoader] Failed to parse .env file:', error.message);
    return {};
  }
}

/**
 * 環境変数をプロセスに設定
 * @param {Object} envVars - .envから読み込んだ環境変数
 */
function loadEnvironmentVariables(envVars) {
  let loadedCount = 0;

  Object.entries(envVars).forEach(([key, value]) => {
    // 既存の環境変数より優先（上書きしない）
    if (process.env[key] === undefined) {
      process.env[key] = value;
      loadedCount++;
    }
  });

  if (loadedCount > 0) {
    console.log(`[EnvLoader] Loaded ${loadedCount} environment variables from .env`);
  }
}

/**
 * .envファイルをロードし、環境変数に反映
 * @param {string} customPath - カスタムパス（オプション）
 * @returns {Object} 読み込んだ環境変数
 */
function loadEnv(customPath = null) {
  const envPath = customPath || getEnvPath();
  const envVars = parseEnvFile(envPath);
  
  if (Object.keys(envVars).length > 0) {
    loadEnvironmentVariables(envVars);
  }

  return envVars;
}

/**
 * 特定の環境変数を取得（.env優先）
 * @param {string} key - 環境変数名
 * @returns {string|null} 環境変数値
 */
function getEnv(key) {
  // プロセス環境変数を優先（システム設定などが優先）
  return process.env[key] || null;
}

/**
 * LLMプール用のAPIキーを取得
 * @returns {Object} 各プロバイダーのAPIキー
 */
function getLLMProviderKeys() {
  return {
    MINIMAX_API_KEY: getEnv('MINIMAX_API_KEY'),
    GLM_API_KEY: getEnv('GLM_API_KEY'),
    KIMI_API_KEY: getEnv('KIMI_API_KEY'),
    ANTHROPIC_API_KEY: getEnv('ANTHROPIC_API_KEY')
  };
}

/**
 * コマンドライン引数に基づいてロードするか判定
 * @returns {boolean} .envをロードすべきかどうか
 */
function shouldLoadEnvFromArgs() {
  const args = process.argv.slice(2);
  // --status, --test, --help オプション時はロードしない
  const skipLoadOptions = ['--status', '--test', '--help', '-h'];
  return !args.some(arg => skipLoadOptions.includes(arg));
}

// モジュールエクスポート
if (require.main === module) {
  // 直接実行された場合：.envをロードして環境変数を表示
  if (shouldLoadEnvFromArgs()) {
    const envVars = loadEnv();
    
    console.log('\n=== Current Environment Variables ===');
    const providerKeys = getLLMProviderKeys();
    
    Object.entries(providerKeys).forEach(([key, value]) => {
      const maskedValue = value ? `${value.slice(0, 8)}${'.'.repeat(value.length > 8 ? value.length - 8 : 0)}` : 'Not set';
      console.log(`${key}: ${maskedValue}`);
    });
    
    console.log('===================================\n');
  }
}

module.exports = {
  loadEnv,
  getEnv,
  getLLMProviderKeys,
  getEnvPath,
  parseEnvFile,
  shouldLoadEnvFromArgs
};
