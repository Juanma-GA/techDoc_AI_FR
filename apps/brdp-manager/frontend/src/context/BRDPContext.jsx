import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { fetchBRDPs, saveBRDPs, resetToDemoBRDPs } from '../services/api';

const BRDPContext = createContext();

export function BRDPProvider({ children }) {
  const [brdps, setBrdpsState] = useState([]);

  const [selectedBRDPs, setSelectedBRDPs] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadBRDPs = async () => {
      try {
        const data = await fetchBRDPs();
        setBrdpsState(data);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch BRDPs from server:', err);
        setError(err.message);
      } finally {
        setIsLoading(false);
      }
    };

    loadBRDPs();
  }, []);

  const setBrdps = useCallback(async (newBrdps) => {
    setBrdpsState(newBrdps);
    try {
      await saveBRDPs(newBrdps);
    } catch (err) {
      console.error('Failed to save BRDPs to server:', err);
    }
  }, []);

  const updateBRDP = useCallback((id, changes) => {
    const updated = brdps.map(b => {
      if (b.id !== id) return b;

      const history = b.history || [];
      const fieldsToTrack = ['proposal', 'comment', 'validation'];

      Object.keys(changes).forEach(field => {
        if (fieldsToTrack.includes(field) && changes[field] !== b[field]) {
          history.push({
            date: new Date().toISOString(),
            field,
            oldValue: b[field] || '',
            newValue: changes[field] || '',
          });
        }
      });

      return { ...b, ...changes, history };
    });
    setBrdps(updated);
  }, [brdps, setBrdps]);

  const resetToMock = useCallback(async () => {
    try {
      const demo = await resetToDemoBRDPs();
      setBrdpsState(demo);
    } catch (err) {
      console.error('Failed to reset BRDPs on server:', err);
    }
  }, []);

  const stats = {
    total: brdps.length,
    validated: brdps.filter((brdp) => brdp.validation === 'Validated').length,
    refused: brdps.filter((brdp) => brdp.validation === 'Refused').length,
    pending: brdps.filter((brdp) => brdp.validation === 'Pending').length,
  };

  const value = {
    brdps,
    setBrdps,
    updateBRDP,
    resetToMock,
    stats,
    selectedBRDPs,
    setSelectedBRDPs,
    isLoading,
    error,
    get selectedBRDP() {
      return selectedBRDPs.length > 0 ? selectedBRDPs[0] : null;
    },
    setSelectedBRDP: (brdp) => {
      setSelectedBRDPs(brdp ? [brdp] : []);
    },
  };

  return (
    <BRDPContext.Provider value={value}>
      {children}
    </BRDPContext.Provider>
  );
}

export function useBRDPContext() {
  const context = useContext(BRDPContext);
  if (!context) {
    throw new Error('useBRDPContext must be used within BRDPProvider');
  }
  return context;
}
