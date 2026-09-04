import { useState } from 'react';
import { useAPIKey } from '../hooks/useAPIKey';

/**
 * Mistral configuration card — same layout/classes as every other ATEXIS POC's
 * Settings page (`.card` + `.switch-row` LLM toggle + `.form` fields +
 * `.btn primary/secondary` + `.badge` + `.success`/`.error` feedback).
 */
export default function AIConfigSection() {
  const {
    apiKeySet,
    baseUrl,
    modelName,
    embedModel,
    llmEnabled,
    saveKey,
    setEnabled,
    testConnection,
    isLoading,
  } = useAPIKey();

  const [apiKeyInput, setApiKeyInput] = useState('');
  const [modelInput, setModelInput] = useState('');
  const [embedModelInput, setEmbedModelInput] = useState('');
  const [baseUrlInput, setBaseUrlInput] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [feedback, setFeedback] = useState(null);

  if (isLoading) return null;

  const handleSave = async () => {
    setFeedback(null);
    setIsSaving(true);
    try {
      await saveKey({
        apiKey: apiKeyInput || undefined,
        model: modelInput || modelName || undefined,
        embedModel: embedModelInput || embedModel || undefined,
        base: baseUrlInput || baseUrl || undefined,
      });
      setApiKeyInput('');
      setFeedback({ kind: 'ok', text: 'Paramètres enregistrés.' });
    } catch (err) {
      setFeedback({ kind: 'error', text: err.message || 'Échec de la sauvegarde.' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setFeedback(null);
    setIsTesting(true);
    try {
      const result = await testConnection();
      setFeedback(
        result.ok
          ? { kind: 'ok', text: `Connexion OK (${result.models?.length ?? 0} modèles disponibles).` }
          : { kind: 'error', text: `Échec : ${result.error ?? ''}` }
      );
    } catch (err) {
      setFeedback({ kind: 'error', text: err.message || 'Échec de la connexion.' });
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <>
      <div className="card">
        <h2 className="card-title">Intelligence artificielle</h2>
        <div className="switch-row">
          <div>
            <div className="label">LLM activé</div>
            <small style={{ color: 'var(--fg-dim)', fontSize: '0.78rem' }}>
              Désactiver saute les tâches confiées à l'IA (extraction, génération, assistant). La
              clé Mistral est conservée.
            </small>
          </div>
          <label className="switch">
            <input type="checkbox" checked={llmEnabled} onChange={(e) => setEnabled(e.target.checked)} />
            <span className="track" />
          </label>
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
            Configuration Mistral
            {apiKeySet ? (
              <span className="badge ok">CONFIGURED</span>
            ) : (
              <span className="badge warn">NOT CONFIGURED</span>
            )}
          </span>
        </h2>
        <div className="form">
          <label>
            <div className="label">Clé API Mistral</div>
            <input
              className="input"
              type="password"
              autoComplete="off"
              placeholder="sk-..."
              value={apiKeyInput}
              onChange={(e) => setApiKeyInput(e.target.value)}
            />
            {apiKeySet ? (
              <small style={{ color: 'var(--fg-dim)', fontSize: '0.78rem' }}>
                Une clé est déjà enregistrée (laisser vide pour la conserver).
              </small>
            ) : null}
          </label>
          <label>
            <div className="label">Base URL</div>
            <input
              className="input"
              type="url"
              value={baseUrlInput}
              onChange={(e) => setBaseUrlInput(e.target.value)}
              placeholder={baseUrl || 'https://api.mistral.ai'}
            />
          </label>
          <div className="row">
            <label className="grow">
              <div className="label">Modèle chat</div>
              <input
                className="input"
                value={modelInput}
                onChange={(e) => setModelInput(e.target.value)}
                placeholder={modelName || 'mistral-small-latest'}
              />
            </label>
            <label className="grow">
              <div className="label">Modèle embeddings</div>
              <input
                className="input"
                value={embedModelInput}
                onChange={(e) => setEmbedModelInput(e.target.value)}
                placeholder={embedModel || 'mistral-embed'}
              />
            </label>
          </div>
          <div className="row">
            <button type="button" className="btn primary" disabled={isSaving} onClick={handleSave}>
              Enregistrer
            </button>
            <button type="button" className="btn secondary" disabled={isTesting} onClick={handleTestConnection}>
              Tester la connexion
            </button>
          </div>
          {feedback ? <div className={feedback.kind === 'ok' ? 'success' : 'error'}>{feedback.text}</div> : null}
        </div>
      </div>
    </>
  );
}
