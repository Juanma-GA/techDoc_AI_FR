import { useState, useEffect, useCallback } from 'react';
import { fetchConfig, saveConfig } from '../services/api';

const DEFAULT_CONFIG = {
  projectName: '',
  modelIdentCode: '',
  systemDiffCode: 'A',
  issueNumber: '001',
  inWork: '00',
  languageIsoCode: 'en',
  countryIsoCode: 'US',
  securityClassification: '01',
  enterpriseCode: '',
};

// Backend (snake_case, /api/v1/project-config) <-> frontend (camelCase) mapping.
function fromApi(data) {
  return {
    projectName: data.project_name ?? '',
    modelIdentCode: data.model_ident_code ?? '',
    systemDiffCode: data.system_diff_code ?? 'A',
    issueNumber: data.issue_number ?? '001',
    inWork: data.in_work ?? '00',
    languageIsoCode: data.language_iso ?? 'en',
    countryIsoCode: data.country_iso ?? 'US',
    securityClassification: data.security_classification ?? '01',
    enterpriseCode: data.enterprise_code ?? '',
  };
}

function toApi(config) {
  return {
    project_name: config.projectName,
    model_ident_code: config.modelIdentCode,
    system_diff_code: config.systemDiffCode,
    issue_number: config.issueNumber,
    in_work: config.inWork,
    language_iso: config.languageIsoCode,
    country_iso: config.countryIsoCode,
    security_classification: config.securityClassification,
    enterprise_code: config.enterpriseCode,
  };
}

export function useProjectConfig() {
  const [projectConfig, setProjectConfig] = useState(DEFAULT_CONFIG);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        const data = await fetchConfig();
        setProjectConfig({ ...DEFAULT_CONFIG, ...fromApi(data) });
        setError(null);
      } catch (err) {
        console.error('Failed to fetch config from server:', err);
        setError(err.message);
      } finally {
        setIsLoading(false);
      }
    };

    loadConfig();
  }, []);

  const saveProjectConfig = useCallback(async (config) => {
    setProjectConfig(config);
    try {
      await saveConfig(toApi(config));
    } catch (err) {
      console.error('Failed to save config to server:', err);
    }
  }, []);

  return {
    projectConfig,
    saveProjectConfig,
    isLoading,
    error,
  };
}
