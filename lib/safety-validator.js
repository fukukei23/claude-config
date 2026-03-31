/**
 * セーフティバリデーター
 * 操作の安全性評価と自動承認/確認/ブロックの判定
 */

class SafetyValidator {
  // 危険な一括削除パターン
  static BULK_DELETE_PATTERNS = [
    /rm\s+-rf\s+\*[^\/]/i,           // rm -rf * (ルート以外)
    /rm\s+-rf\s+\/\*/i,            // rm -rf /*
    /rm\s+-rf\s+~\/?\*/i,           // rm -rf ~/*
    /rm\s+-rf\s+\/home\/\*/i,         // rm -rf /home/*
    /Remove-Item.*-Recurse\s+[A-Z]:[\\\/]\*/i,  // Remove-Item -Recurse C:\*
    /Remove-Item.*-Recurse\s+\*[^\/]/i, // Remove-Item -Recurse *
    /del\s+\/q\s+\/s/i,              // del /q /s
    /rmdir\s+\/s\s+\/q/i,             // rmdir /s /q
    /erase\s+\/s\s+\/q/i              // erase /s /q
  ];

  // 保護されたシステムディレクトリ
  static PROTECTED_DIRECTORIES = [
    'C:\\Windows',
    'C:\\Program Files',
    'C:\\Program Files (x86)',
    'C:\\ProgramData',
    'C:\\Boot',
    '/etc',
    '/bin',
    '/usr/bin',
    '/usr/sbin',
    '/boot',
    '/lib',
    '/usr/lib',
    '/sys'
  ];

  // デフォルトの安全ディレクトリ（現在の環境に基づく）
  static DEFAULT_SAFE_DIRECTORIES = [
    '/home/yn441611',
    'C:\\Users\\USER',
    'C:\\Users\\USER\\Projects',
    'C:\\Users\\USER\\code',
    'C:\\Temp',
    '/tmp'
  ];

  // 自動承認されるツール
  static AUTO_APPROVE_TOOLS = [
    'read_file',
    'read_multiple_files',
    'write_file',
    'read_page',
    'get_page_text',
    'list_directory',
    'get_file_info'
  ];

  // 確認が必要なツール
  static CONFIRM_REQUIRED_TOOLS = [
    'move_file',
    'delete_files',
    'start_search',
    'kill_process',
    'mcp__Desktop_Commander__move_file',
    'mcp__Desktop_Commander__force_terminate'
  ];

  // ブロックされるツール（Desktop Commander blockedCommandsに基づく）
  static BLOCKED_COMMANDS = [
    'mkfs', 'format', 'mount', 'umount', 'fdisk', 'dd', 'parted', 'diskpart',
    'sudo', 'su', 'passwd', 'adduser', 'useradd', 'usermod', 'groupadd',
    'chsh', 'visudo', 'shutdown', 'reboot', 'halt', 'poweroff', 'init',
    'iptables', 'firewall', 'netsh', 'sfc', 'bcdedit', 'reg', 'net',
    'sc', 'runas', 'cipher', 'takeown'
  ];

  /**
   * 操作を分類
   * @param {string} toolName - ツール名
   * @param {Object} params - パラメータ
   * @param {Object} settings - セーフティ設定
   * @returns {Object} { tier: 'auto_approve'|'confirm_required'|'blocked', reason: string }
   */
  static classifyOperation(toolName, params = {}, settings = {}) {
    const safety = settings.safety || {};

    // 1. 明示的にブロックされているコマンドをチェック
    if (this.isBlockedCommand(toolName, params)) {
      return {
        tier: 'blocked',
        reason: 'Command is explicitly blocked for safety'
      };
    }

    // 2. パターンブロックチェック（一括削除など）
    const patternBlock = this.checkDangerousPattern(toolName, params);
    if (patternBlock.blocked) {
      return {
        tier: 'blocked',
        reason: patternBlock.reason
      };
    }

    // 3. 保護ディレクトリへのアクセスをチェック
    const protectedDirCheck = this.checkProtectedDirectory(toolName, params);
    if (protectedDirCheck.blocked) {
      return {
        tier: 'blocked',
        reason: protectedDirCheck.reason
      };
    }

    // 4. ツールベースの分類
    if (this.AUTO_APPROVE_TOOLS.includes(toolName)) {
      return {
        tier: 'auto_approve',
        reason: 'Tool is in auto-approve list'
      };
    }

    if (this.CONFIRM_REQUIRED_TOOLS.includes(toolName)) {
      return {
        tier: 'confirm_required',
        reason: 'Tool requires confirmation'
      };
    }

    // 5. start_processの特別チェック
    if (toolName === 'start_process' || toolName === 'mcp__Desktop_Commander__start_process') {
      return this.classifyProcessOperation(params, safety);
    }

    // 6. デフォルト：確認必要
    return {
      tier: 'confirm_required',
      reason: 'Default: confirmation required'
    };
  }

  /**
   * ブロックされたコマンドかチェック
   */
  static isBlockedCommand(toolName, params) {
    // start_processの場合、コマンド文字列をチェック
    if (toolName === 'start_process' && params.command) {
      const cmd = params.command.toLowerCase().split(/\s+/)[0];
      return this.BLOCKED_COMMANDS.includes(cmd);
    }
    return false;
  }

  /**
   * 危険なパターンをチェック
   */
  static checkDangerousPattern(toolName, params) {
    // start_processの場合、コマンド文字列をチェック
    if ((toolName === 'start_process' || toolName === 'mcp__Desktop_Commander__start_process') && params.command) {
      const cmd = params.command;

      for (const pattern of this.BULK_DELETE_PATTERNS) {
        if (pattern.test(cmd)) {
          return {
            blocked: true,
            reason: `Pattern matches dangerous bulk deletion: ${pattern}`
          };
        }
      }
    }

    // パスを含むパラメータをチェック
    for (const key in params) {
      const value = params[key];
      if (typeof value === 'string' && this.isBulkDeletePath(value)) {
        return {
          blocked: true,
          reason: `Path matches bulk deletion pattern: ${value}`
        };
      }
    }

    return { blocked: false };
  }

  /**
   * 一括削除パスかチェック
   */
  static isBulkDeletePath(path) {
    // ルートやホーム全体のワイルドカード
    if (/\*[^\/]*$/.test(path) && !/\/[^\/]+\/.*\*/.test(path)) {
      return true;
    }

    // システムディレクトリの削除
    const normalizedPath = this.normalizePath(path);
    for (const protectedDir of this.PROTECTED_DIRECTORIES) {
      if (normalizedPath.startsWith(this.normalizePath(protectedDir))) {
        return true;
      }
    }

    return false;
  }

  /**
   * 保護ディレクトリへのアクセスをチェック
   */
  static checkProtectedDirectory(toolName, params) {
    // パスを含むパラメータを抽出
    const paths = this.extractPathsFromParams(toolName, params);

    for (const path of paths) {
      const normalizedPath = this.normalizePath(path);

      for (const protectedDir of this.PROTECTED_DIRECTORIES) {
        const normalizedProtected = this.normalizePath(protectedDir);
        if (normalizedPath.startsWith(normalizedProtected)) {
          return {
            blocked: true,
            reason: `Access to protected directory: ${path}`
          };
        }
      }
    }

    return { blocked: false };
  }

  /**
   * パラメータからパスを抽出
   */
  static extractPathsFromParams(toolName, params) {
    const paths = [];

    // パスを含む可能性のあるパラメータ名
    const pathKeys = ['path', 'file_path', 'source', 'destination', 'directory'];

    for (const key of pathKeys) {
      if (params[key]) {
        if (Array.isArray(params[key])) {
          paths.push(...params[key]);
        } else {
          paths.push(params[key]);
        }
      }
    }

    return paths;
  }

  /**
   * プロセス操作を分類
   */
  static classifyProcessOperation(params, safety) {
    const { command } = params;

    if (!command) {
      return {
        tier: 'auto_approve',
        reason: 'Empty command (safe)'
      };
    }

    // テスト・ビルドコマンドは自動承認
    const autoApproveCommands = [
      /npm\s+test/i, /pytest/i, /make\s+test/i,
      /npm\s+run\s+build/i, /make\s+build/i,
      /npm\s+install/i, /pip\s+install/i,
      /npm\s+run\s+dev/i,
      /git\s+(add|commit|status|log|diff)/i,
      /ls/i, /dir/i, /cat/i, /grep/i, /find/i
    ];

    for (const pattern of autoApproveCommands) {
      if (pattern.test(command)) {
        return {
          tier: 'auto_approve',
          reason: `Command matches auto-approve pattern: ${pattern}`
        };
      }
    }

    // Gitの危険な操作は確認必要
    if (/git\s+(push|pull|merge|reset\s+--hard)/i.test(command)) {
      return {
        tier: 'confirm_required',
        reason: 'Git operation requires confirmation'
      };
    }

    // デフォルト：確認必要
    return {
      tier: 'confirm_required',
      reason: 'Process command requires confirmation'
    };
  }

  /**
   * パスを正規化（Windows/WSL統合）
   */
  static normalizePath(path) {
    if (!path) return '';

    // WSLパスをWindowsパスに変換
    if (path.startsWith('/mnt/c/')) {
      return path.replace('/mnt/c/', 'C:\\').replace(/\//g, '\\\\');
    }

    // Windowsパスを統一形式に
    if (path.includes('\\')) {
      return path.replace(/\\/g, '\\\\');
    }

    return path;
  }

  /**
   * 安全ディレクトリかチェック
   */
  static isInSafeDirectory(path, settings = {}) {
    const safety = settings.safety || {};
    const safeDirs = safety.safeDirectories || this.DEFAULT_SAFE_DIRECTORIES;

    const normalizedPath = this.normalizePath(path);

    for (const safeDir of safeDirs) {
      const normalizedSafe = this.normalizePath(safeDir);
      if (normalizedPath.startsWith(normalizedSafe)) {
        return true;
      }
    }

    return false;
  }

  /**
   * バルク操作かチェック
   */
  static isBulkOperation(params, threshold = 10) {
    // 複数のファイルパラメータがある場合
    for (const key in params) {
      const value = params[key];
      if (Array.isArray(value) && value.length > threshold) {
        return {
          isBulk: true,
          count: value.length,
          threshold
        };
      }
    }

    // ファイルサイズチェック
    if (params.content && typeof params.content === 'string') {
      const sizeKB = params.content.length / 1024;
      if (sizeKB > threshold) {
        return {
          isBulk: true,
          sizeKB: Math.round(sizeKB * 100) / 100,
          threshold
        };
      }
    }

    return { isBulk: false };
  }

  /**
   * バリデーション結果を表示
   */
  static printClassificationResult(toolName, classification) {
    const icons = {
      'auto_approve': '✓',
      'confirm_required': '⚠️',
      'blocked': '❌'
    };

    console.log(`${icons[classification.tier]} ${toolName}: ${classification.tier}`);
    console.log(`  Reason: ${classification.reason}`);
  }

  /**
   * CLAUDE.mdからプロジェクト固有の設定を読み込み
   */
  static loadProjectConfig(projectPath) {
    // プロジェクト固有のCLAUDE.mdがあれば読み込む
    // 実装は環境に応じて調整
    return {};
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = SafetyValidator;
}
