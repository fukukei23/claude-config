/**
 * LLMフェイルオーバークライアント
 * API呼び出しにLLMプールのフェイルオーバー機能を追加
 */

const LLMPoolManager = require('./llm-pool-manager');

class LLMFallbackClient {
  constructor(settings, originalAPIClient) {
    this.poolManager = new LLMPoolManager(settings);
    this.originalAPIClient = originalAPIClient;
    this.maxRetries = 5;
    this.callCount = 0;
    this.fallbackCount = 0;
  }

  /**
   * API呼び出しにフェイルオーバーロジックを適用
   * @param {string} prompt - プロンプト
   * @param {Object} options - APIオプション
   */
  async callWithFallback(prompt, options = {}) {
    if (!this.poolManager.enabled) {
      return this.originalAPIClient.call(prompt, options);
    }

    this.callCount++;
    let lastError;
    let attempts = 0;
    let lastProvider = null;

    while (attempts < this.maxRetries) {
      const provider = this.poolManager.getNextAvailableProvider();

      // 全プロバイダーがクールダウン中の場合
      if (!provider) {
        console.warn('[LLM Fallback] All providers in cooldown, resetting...');
        this.poolManager.resetPool();
        attempts++;
        continue;
      }

      lastProvider = provider;
      console.log(`[LLM Fallback] Attempt ${attempts + 1}/${this.maxRetries} using ${provider.name} ($${provider.costPer1kTokens}/1K tokens)`);

      try {
        // プロバイダー設定で環境変数を一時的に設定
        const originalEnv = { ...process.env };
        const providerConfig = this.poolManager.getCurrentProviderConfig(provider);
        
        Object.assign(process.env, {
          ANTHROPIC_AUTH_TOKEN: providerConfig.ANTHROPIC_AUTH_TOKEN,
          ANTHROPIC_BASE_URL: providerConfig.ANTHROPIC_BASE_URL
        });

        const result = await this.originalAPIClient.call(prompt, {
          ...options,
          model: provider.model
        });

        // 成功したらクールダウン解除
        this.poolManager.markSuccess(provider.id);

        // 環境変数を元に戻す
        Object.assign(process.env, originalEnv);

        console.log(`[LLM Fallback] Success with ${provider.name}`);
        return result;

      } catch (error) {
        lastError = error;
        this.poolManager.markFailure(provider.id);
        this.fallbackCount++;
        attempts++;
        
        console.warn(`[LLM Fallback] ${provider.name} failed: ${error.message}`);
        console.warn(`[LLM Fallback] Trying next provider...`);
      }
    }

    // 全てのプロバイダーが失敗
    console.error(`[LLM Fallback] All ${this.maxRetries} providers failed`);
    console.error(`[LLM Fallback] Total calls: ${this.callCount}, Total fallbacks: ${this.fallbackCount}`);
    
    throw new Error(
      `All LLM providers failed after ${this.maxRetries} attempts. ` +
      `Last provider: ${lastProvider?.name}. ` +
      `Last error: ${lastError?.message}`
    );
  }

  /**
   * 現在のアクティブプロバイダーを取得
   */
  getCurrentProvider() {
    return this.poolManager.getNextAvailableProvider();
  }

  /**
   * プバイダーステータスを表示
   */
  printStatus() {
    const stats = this.poolManager.getStats();
    const providers = this.poolManager.getProviderStatus();

    console.log('\n=== LLM Pool Status ===');
    console.log(`Enabled: ${stats.enabled}`);
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
   * 統計情報を取得
   */
  getStats() {
    return {
      ...this.poolManager.getStats(),
      totalCalls: this.callCount,
      totalFallbacks: this.fallbackCount,
      successRate: this.callCount > 0 
        ? ((this.callCount - this.fallbackCount) / this.callCount * 100).toFixed(2) + '%'
        : 'N/A'
    };
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = LLMFallbackClient;
}
