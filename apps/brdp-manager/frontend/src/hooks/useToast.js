import { useState, useCallback } from 'react';

/**
 * Custom hook for managing toast notifications
 * @returns {Object} Toast management object
 * @property {Array} toasts - Array of active toasts
 * @property {Function} showToast - Show a new toast
 * @property {Function} removeToast - Remove a toast by ID
 */
export function useToast() {
  const [toasts, setToasts] = useState([]);

  /**
   * Show a new toast notification
   * @param {string} message - Toast message
   * @param {string} type - Toast type: 'success', 'error', 'warning', 'info'
   */
  const showToast = useCallback((message, type = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);

    // Auto-remove after 3 seconds
    setTimeout(() => {
      removeToast(id);
    }, 3000);

    return id;
  }, []);

  /**
   * Remove a toast by ID
   * @param {string|number} id - Toast ID to remove
   */
  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  }, []);

  return {
    toasts,
    showToast,
    removeToast,
  };
}
