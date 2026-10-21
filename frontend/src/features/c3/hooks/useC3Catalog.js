import { useState, useEffect } from 'react';
import { c3Api } from '../api.js';

export const useC3Catalog = () => {
  const [catalog, setCatalog] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    setIsLoading(true);
    setError(null);

    c3Api
      .getFaultCatalog(controller.signal)
      .then((data) => {
        if (mounted) {
          setCatalog(data);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (mounted && err.name !== 'AbortError') {
          setError(err.message || 'Failed to fetch fault catalog');
          setIsLoading(false);
        }
      });

    return () => {
      mounted = false;
      controller.abort();
    };
  }, []);

  return { catalog, isLoading, error };
};
