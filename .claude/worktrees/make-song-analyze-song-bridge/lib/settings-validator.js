/**
 * 設定バリデーター
 * LLMプール設定を含むsettings.jsonのバリデーション
 */

class SettingsValidator {
  /**
   * LLMプール設定のバリデーション
   * @param {Object} settings - settings.jsonオブジェクト
   * @returns {Object} { valid: boolean, errors: string[], warnings: string[] }
   */
  static validateLLMPool(settings) {
    const errors = [];
    const warnings = [];

    if (!settings.llmPool) {
      return { valid: true, errors: [], warnings: ['llmPool not configured, using default API'] };
    }

    const pool = settings.llmPool;

    // enabledチェック
    if (typeof pool.enabled !== 'boolean') {
      errors.push('llmPool.enabled must be a boolean');
    }

    // cooldownPeriodチェック
    if (pool.cooldownPeriod !== undefined) {
      if (typeof pool.cooldownPeriod !== 'number' || pool.cooldownPeriod < 0) {
        errors.push('llmPool.cooldownPeriod must be a non-negative number');
      }
    }

    // providersチェック
    if (!Array.isArray(pool.providers)) {
      errors.push('llmPool.providers must be an array');
      return { valid: false, errors, warnings };
    }

    if (pool.providers.length === 0) {
      warnings.push('llmPool.providers is empty, no fallback providers available');
    }

    // 各プロバイダーのチェック
    const providerIds = new Set();
    const priorities = new Set();

    pool.providers.forEach((provider, index) => {
      const prefix = `llmPool.providers[${index}]`;

      // 必須フィールド
      const requiredFields = ['name', 'id', 'model', 'baseURL', 'apiKey', 'costPer1kTokens', 'priority'];
      requiredFields.forEach(field => {
        if (!provider[field]) {
          errors.push(`${prefix}.${field} is required`);
        }
      });

      // idの重複チェック
      if (provider.id) {
        if (providerIds.has(provider.id)) {
          errors.push(`${prefix}.id "${provider.id}" is duplicated`);
        }
        providerIds.add(provider.id);
      }

      // priorityの重複チェック
      if (provider.priority !== undefined) {
        if (typeof provider.priority !== 'number' || provider.priority < 1) {
          errors.push(`${prefix}.priority must be a positive number`);
        }
        if (priorities.has(provider.priority)) {
          warnings.push(`${prefix}.priority ${provider.priority} is duplicated`);
        }
        priorities.add(provider.priority);
      }

      // costPer1kTokensチェック
      if (provider.costPer1kTokens !== undefined) {
        if (typeof provider.costPer1kTokens !== 'number' || provider.costPer1kTokens < 0) {
          errors.push(`${prefix}.costPer1kTokens must be a non-negative number`);
        }
      }

      // baseURLチェック
      if (provider.baseURL && typeof provider.baseURL === 'string') {
        try {
          new URL(provider.baseURL);
        } catch {
          errors.push(`${prefix}.baseURL "${provider.baseURL}" is not a valid URL`);
        }
      }

      // activeチェック
      if (provider.active !== undefined && typeof provider.active !== 'boolean') {
        errors.push(`${prefix}.active must be a boolean`);
      }

      // lastFailureチェック
      if (provider.lastFailure !== undefined && provider.lastFailure !== null) {
        if (typeof provider.lastFailure !== 'number' || provider.lastFailure < 0) {
          errors.push(`${prefix}.lastFailure must be a timestamp number or null`);
        }
      }

      // fallbackCountチェック
      if (provider.fallbackCount !== undefined) {
        if (typeof provider.fallbackCount !== 'number' || provider.fallbackCount < 0) {
          errors.push(`${prefix}.fallbackCount must be a non-negative number`);
        }
      }
    });

    // APIキーの環境変数チェック
    pool.providers.forEach(provider => {
      if (provider.apiKey && !process.env[provider.apiKey] && !provider.apiKey.startsWith('sk-')) {
        warnings.push(
          `Provider "${provider.name}" apiKey "${provider.apiKey}" not found in environment variables. ` +
          'Ensure the API key is set in env or use direct key value.'
        );
      }
    });

    const valid = errors.length === 0;

    return { valid, errors, warnings };
  }

  /**
   * 完全なsettings.jsonバリデーション
   * @param {Object} settings - settings.jsonオブジェクト
   * @returns {Object} { valid: boolean, errors: string[], warnings: string[] }
   */
  static validateAll(settings) {
    const errors = [];
    const warnings = [];

    // 既存のバリデーション
    if (!settings.env) {
      warnings.push('settings.env is missing');
    }

    // LLMプールバリデーション
    const llmPoolResult = this.validateLLMPool(settings);
    errors.push(...llmPoolResult.errors);
    warnings.push(...llmPoolResult.warnings);

    // パーミッション設定バリデーション
    const permissionsResult = this.validatePermissions(settings);
    errors.push(...permissionsResult.errors);
    warnings.push(...permissionsResult.warnings);

    return {
      valid: errors.length === 0,
      errors,
      warnings
    };
  }

  /**
   * パーミッション設定のバリデーション
   * @param {Object} settings - settings.jsonオブジェクト
   * @returns {Object} { valid: boolean, errors: string[], warnings: string[] }
   */
  static validatePermissions(settings) {
    const errors = [];
    const warnings = [];

    if (!settings.permissions) {
      warnings.push('settings.permissions is missing');
      return { valid: true, errors, warnings };
    }

    const perms = settings.permissions;

    // allowチェック
    if (perms.allow !== undefined && !Array.isArray(perms.allow)) {
      errors.push('permissions.allow must be an array');
    }

    // denyチェック
    if (perms.deny !== undefined && !Array.isArray(perms.deny)) {
      errors.push('permissions.deny must be an array');
    }

    // askチェック
    if (perms.ask !== undefined && !Array.isArray(perms.ask)) {
      errors.push('permissions.ask must be an array');
    }

    // defaultModeチェック
    if (perms.defaultMode !== undefined) {
      const validModes = ['acceptEdits', 'bypassPermissions', 'default', 'delegate', 'dontAsk', 'plan'];
      if (!validModes.includes(perms.defaultMode)) {
        errors.push(`permissions.defaultMode must be one of: ${validModes.join(', ')}`);
      }
    }

    return { valid: errors.length === 0, errors, warnings };
  }

  /**
   * バリデーション結果を表示
   * @param {Object} result - validateAllの戻り値
   */
  static printValidationResult(result) {
    if (result.valid && result.warnings.length === 0) {
      console.log('✓ Settings are valid');
      return;
    }

    if (result.errors.length > 0) {
      console.error('\n❌ Settings Errors:');
      result.errors.forEach(error => console.error(`  - ${error}`));
    }

    if (result.warnings.length > 0) {
      console.warn('\n⚠️  Settings Warnings:');
      result.warnings.forEach(warning => console.warn(`  - ${warning}`));
    }

    if (result.valid) {
      console.log('\n✓ Settings are valid (with warnings)');
    }
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = SettingsValidator;
}
