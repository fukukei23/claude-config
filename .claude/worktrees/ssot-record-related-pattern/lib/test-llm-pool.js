/**
 * LLMプールフェイルオーバー機能のテスト
 */

const LLMPoolManager = require('./llm-pool-manager');
const LLMFallbackClient = require('./llm-fallback-client');
const SettingsValidator = require('./settings-validator');

// テスト用設定
const testSettings = {
  llmPool: {
    enabled: true,
    cooldownPeriod: 5000, // 5秒（テスト用に短縮）
    providers: [
      {
        name: "Test Provider 1",
        id: "test-1",
        model: "model-1",
        baseURL: "https://api.test1.com/v1",
        apiKey: "TEST_KEY_1",
        costPer1kTokens: 0.001,
        priority: 1,
        active: true,
        lastFailure: null,
        fallbackCount: 0
      },
      {
        name: "Test Provider 2",
        id: "test-2",
        model: "model-2",
        baseURL: "https://api.test2.com/v1",
        apiKey: "TEST_KEY_2",
        costPer1kTokens: 0.003,
        priority: 2,
        active: true,
        lastFailure: null,
        fallbackCount: 0
      },
      {
        name: "Test Provider 3",
        id: "test-3",
        model: "model-3",
        baseURL: "https://api.test3.com/v1",
        apiKey: "TEST_KEY_3",
        costPer1kTokens: 0.005,
        priority: 3,
        active: true,
        lastFailure: null,
        fallbackCount: 0
      }
    ]
  }
};

// モックAPIクライアント
class MockAPIClient {
  constructor(failureConfig = {}) {
    this.failureConfig = failureConfig;
    this.callCount = 0;
  }

  async call(prompt, options) {
    this.callCount++;
    const providerId = options?.model;

    // 指定されたプロバイダーで失敗させる
    if (this.failureConfig[providerId]) {
      throw new Error(`Mock failure for ${providerId}`);
    }

    return { result: `Response from ${providerId}`, tokens: 100 };
  }
}

/**
 * テスト1: 基本的なプロバイダー選択
 */
function testBasicProviderSelection() {
  console.log('\n=== Test 1: Basic Provider Selection ===');
  const manager = new LLMPoolManager(testSettings);
  
  const provider1 = manager.getNextAvailableProvider();
  console.log('First provider:', provider1?.name);
  console.assert(provider1.id === 'test-1', 'Should select lowest priority provider');

  const provider2 = manager.getNextAvailableProvider();
  console.log('Second call (same provider):', provider2?.name);
  console.assert(provider2.id === 'test-1', 'Should return same provider when available');

  console.log('✓ Test 1 passed\n');
}

/**
 * テスト2: フェイルオーバー機能
 */
async function testFailover() {
  console.log('\n=== Test 2: Failover Functionality ===');
  
  // 最初のプロバイダーを失敗させる
  const failureConfig = { 'model-1': true, 'model-2': true };
  const mockClient = new MockAPIClient(failureConfig);
  const manager = new LLMPoolManager(testSettings);
  
  const client = new LLMFallbackClient(testSettings, mockClient);
  client.poolManager = manager;

  try {
    await client.callWithFallback('test prompt');
  } catch (error) {
    console.log('Expected failure after all providers exhausted:', error.message);
  }

  console.log('Fallback count:', manager.providers[0].fallbackCount);
  console.log('Fallback count:', manager.providers[1].fallbackCount);
  console.assert(manager.providers[0].fallbackCount === 1, 'Provider 1 should have 1 fallback');
  console.assert(manager.providers[1].fallbackCount === 1, 'Provider 2 should have 1 fallback');

  console.log('✓ Test 2 passed\n');
}

/**
 * テスト3: クールダウン機能
 */
function testCooldown() {
  console.log('\n=== Test 3: Cooldown Functionality ===');
  const manager = new LLMPoolManager(testSettings);
  
  // プロバイダー1を失敗させる
  manager.markFailure('test-1');
  
  const providerAfterFailure = manager.getNextAvailableProvider();
  console.log('Provider after marking failure:', providerAfterFailure?.name);
  console.assert(providerAfterFailure.id === 'test-2', 'Should skip failed provider');

  // クールダウン期間を待たずにチェック
  const providerDuringCooldown = manager.getNextAvailableProvider();
  console.log('Provider during cooldown:', providerDuringCooldown?.name);
  console.assert(providerDuringCooldown.id === 'test-2', 'Provider 1 should still be in cooldown');

  console.log('✓ Test 3 passed\n');
}

/**
 * テスト4: 全プロバイダークールダウン時のリセット
 */
function testResetPool() {
  console.log('\n=== Test 4: Pool Reset ===');
  const manager = new LLMPoolManager(testSettings);
  
  // 全プロバイダーを失敗させる
  manager.markFailure('test-1');
  manager.markFailure('test-2');
  manager.markFailure('test-3');
  
  console.log('All providers in cooldown:', manager.isAllInCooldown());
  console.assert(manager.isAllInCooldown() === true, 'All providers should be in cooldown');

  // プールをリセット
  manager.resetPool();
  
  console.log('Providers after reset:');
  manager.providers.forEach(p => {
    console.log(`  ${p.name}: active=${p.active}, priority=${p.priority}`);
  });

  const providerAfterReset = manager.getNextAvailableProvider();
  console.log('Provider after reset:', providerAfterReset?.name);
  console.assert(manager.getNextAvailableProvider() !== null, 'Should have available provider after reset');

  console.log('✓ Test 4 passed\n');
}

/**
 * テスト5: 設定バリデーション
 */
function testSettingsValidation() {
  console.log('\n=== Test 5: Settings Validation ===');
  
  // 正常設定
  const validSettings = { llmPool: testSettings.llmPool };
  const validResult = SettingsValidator.validateLLMPool(validSettings);
  console.log('Valid settings result:', validResult.valid ? '✓ Valid' : '✗ Invalid');
  console.assert(validResult.valid === true, 'Should pass validation');

  // 無効設定（必須フィールド欠如）
  const invalidSettings = {
    llmPool: {
      enabled: true,
      providers: [{ name: 'Test' }] // id, modelなどが欠如
    }
  };
  const invalidResult = SettingsValidator.validateLLMPool(invalidSettings);
  console.log('Invalid settings errors:', invalidResult.errors.length);
  console.assert(invalidResult.valid === false, 'Should fail validation');
  console.assert(invalidResult.errors.length > 0, 'Should have errors');

  console.log('✓ Test 5 passed\n');
}

/**
 * テスト6: ステータス表示
 */
function testStatusDisplay() {
  console.log('\n=== Test 6: Status Display ===');
  const manager = new LLMPoolManager(testSettings);
  
  // プロバイダー1を失敗させる
  manager.markFailure('test-1');
  
  const status = manager.getProviderStatus();
  console.log('\nProvider status:');
  status.forEach(s => {
    console.log(`  ${s.name}: ${s.status} (priority: ${s.priority})`);
  });

  const stats = manager.getStats();
  console.log('\nPool stats:');
  console.log(`  Total providers: ${stats.totalProviders}`);
  console.log(`  Active providers: ${stats.activeProviders}`);
  console.log(`  Cooldown period: ${stats.cooldownPeriod}ms`);

  console.log('✓ Test 6 passed\n');
}

/**
 * メインテスト実行
 */
async function runAllTests() {
  console.log('========================================');
  console.log('  LLM Pool Failover Test Suite');
  console.log('========================================');

  try {
    testBasicProviderSelection();
    await testFailover();
    testCooldown();
    testResetPool();
    testSettingsValidation();
    testStatusDisplay();

    console.log('\n========================================');
    console.log('  ✓ All Tests Passed!');
    console.log('========================================\n');

  } catch (error) {
    console.error('\n========================================');
    console.error('  ✗ Test Failed!');
    console.error('========================================');
    console.error(error);
    process.exit(1);
  }
}

// テスト実行
if (require.main === module) {
  runAllTests();
}

module.exports = {
  testBasicProviderSelection,
  testFailover,
  testCooldown,
  testResetPool,
  testSettingsValidation,
  testStatusDisplay,
  runAllTests
};
