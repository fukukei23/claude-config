/**
 * LLMプールマネージャー
 * 複数のLLMプロバイダーを管理し、失敗時に自動的にフェイルオーバーする
 */

class LLMPoolManager {
  constructor(settings) {
    this.providers = settings.llmPool?.providers || [];
    this.cooldownPeriod = settings.llmPool?.cooldownPeriod || 300000; // デフォルト5分
    this.enabled = settings.llmPool?.enabled || false;
    this.resetAttempts = 0;
  }

  /**
   * 次の利用可能なプロバイダーを取得（優先順位順）
   */
  getNextAvailableProvider() {
    if (!this.enabled) {
      return null;
    }

    const now = Date.now();
    const available = this.providers
      .filter(p => 
        p.active && 
        (!p.lastFailure || (now - p.lastFailure) > this.cooldownPeriod)
      )
      .sort((a, b) => a.priority - b.priority);

    return available[0] || null;
  }

  /**
   * API呼び出し失敗を記録
   * @param {string} providerId - 失敗したプロバイダーID
   */
  markFailure(providerId) {
    const provider = this.providers.find(p => p.id === providerId);
    if (provider) {
      provider.lastFailure = Date.now();
      provider.fallbackCount++;
      console.warn(`[LLM Pool] Provider "${provider.name}" marked as failed. Total fallbacks: ${provider.fallbackCount}`);
    }
  }

  /**
   * API呼び出し成功を記録（クールダウン解除）
   * @param {string} providerId - 成功したプロバイダーID
   */
  markSuccess(providerId) {
    const provider = this.providers.find(p => p.id === providerId);
    if (provider) {
      provider.lastFailure = null;
      this.updateUsageStats(provider.id, 1000);
      console.log(`[LLM Pool] Provider "${provider.name}" succeeded. Usage updated.`);
    }
  }

  /**
   * 使用量統計の初期化・更新
   * @param {string} providerId - プロバイダーID
   * @param {number} tokens - トークン数
   */
  updateUsageStats(providerId, tokens) {
    const provider = this.providers.find(p => p.id === providerId);
    if (!provider) return;

    if (!provider.usageStats) {
      provider.usageStats = {
        totalRequests: 0,
        totalTokens: 0,
        totalCost: 0,
        lastReset: Date.now()
      };
    }

    provider.usageStats.totalTokens += tokens;
    provider.usageStats.totalRequests++;
    provider.usageStats.totalCost += (tokens / 1000) * provider.costPer1kTokens;
  }

  /**
   * 全プロバイダーがクールダウン中かチェック
   */
  isAllInCooldown() {
    const now = Date.now();
    return this.providers.every(p => 
      !p.active || (p.lastFailure && (now - p.lastFailure) <= this.cooldownPeriod)
    );
  }

  /**
   * プバイダーのステータスを取得
   */
  getProviderStatus() {
    const now = Date.now();
    return this.providers.map(p => ({
      name: p.name,
      id: p.id,
      priority: p.priority,
      active: p.active,
      costPer1kTokens: p.costPer1kTokens,
      fallbackCount: p.fallbackCount,
      status: !p.active ? 'disabled' :
               (p.lastFailure && (now - p.lastFailure) <= this.cooldownPeriod) ? 'cooldown' :
               'available'
    }));
  }

  /**
   * 指定されたプロバイダーを現在の設定として返す
   * 既存のsettings.json構造と互換性を持たせるため
   */
  getCurrentProviderConfig(provider) {
    return {
      ANTHROPIC_AUTH_TOKEN: process.env[provider.apiKey] || provider.apiKey,
      ANTHROPIC_BASE_URL: provider.baseURL,
      ANTHROPIC_DEFAULT_HAIKU_MODEL: provider.model,
      ANTHROPIC_DEFAULT_OPUS_MODEL: provider.model,
      ANTHROPIC_DEFAULT_SONNET_MODEL: provider.model
    };
  }

  /**
   * 統計情報の取得
   */
  getStats() {
    const totalStats = {
      totalRequests: 0,
      totalTokens: 0,
      totalCost: 0
    };

    this.providers.forEach(p => {
      if (p.usageStats) {
        totalStats.totalRequests += p.usageStats.totalRequests || 0;
        totalStats.totalTokens += p.usageStats.totalTokens || 0;
        totalStats.totalCost += p.usageStats.totalCost || 0;
      }
    });

    return {
      enabled: this.enabled,
      cooldownPeriod: this.cooldownPeriod,
      totalProviders: this.providers.length,
      activeProviders: this.providers.filter(p => p.active).length,
      resetAttempts: this.resetAttempts,
      totalFallbacks: this.providers.reduce((sum, p) => sum + p.fallbackCount, 0),
      totalRequests: totalStats.totalRequests,
      totalTokens: totalStats.totalTokens,
      totalCost: totalStats.totalCost.toFixed(4)
    };
  }
}

// Node.js環境用のエクスポート
if (typeof module !== 'undefined' && module.exports) {
  module.exports = LLMPoolManager;
}
