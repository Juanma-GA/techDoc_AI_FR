import { useState, useEffect, useCallback } from 'react';
import { fetchSettings, saveSettings, testSettingsConnection } from '../services/api';

/**
 * Mistral runtime settings — key is stored server-side (STANDARD_POC.md rule #6).
 * The client never holds the raw key: it only knows whether one is configured
 * (`apiKeySet`), the base URL, the chat/embed models, and the `llmEnabled` switch.
 */
export function useAPIKey() {
  const [apiKeySet, setApiKeySet] = useState(false);
  const [baseUrl, setBaseUrl] = useState('');
  const [modelName, setModelName] = useState('');
  const [embedModel, setEmbedModel] = useState('');
  const [llmEnabled, setLlmEnabled] = useState(true);
  const [llmTested, setLlmTested] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchSettings();
      setApiKeySet(!!data.api_key_set);
      setBaseUrl(data.base_url || '');
      setModelName(data.chat_model || '');
      setEmbedModel(data.embed_model || '');
      setLlmEnabled(!!data.llm_enabled);
      setLlmTested(!!data.llm_tested);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch settings from server:', err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const saveKey = useCallback(
    async ({ apiKey, model, base, embedModel: embed } = {}) => {
      await saveSettings({
        api_key: apiKey || undefined,
        chat_model: model || undefined,
        embed_model: embed || undefined,
        base_url: base || undefined,
      });
      await refresh();
    },
    [refresh]
  );

  const setEnabled = useCallback(
    async (enabled) => {
      setLlmEnabled(enabled);
      await saveSettings({ llm_enabled: enabled });
      await refresh();
    },
    [refresh]
  );

  const testConnection = useCallback(async () => {
    const result = await testSettingsConnection();
    await refresh();
    return result;
  }, [refresh]);

  return {
    apiKeySet,
    baseUrl,
    modelName,
    embedModel,
    llmEnabled,
    llmTested,
    setModelName,
    setBaseUrl,
    setEmbedModel,
    saveKey,
    setEnabled,
    testConnection,
    isConfigured: apiKeySet,
    isLoading,
    error,
  };
}
