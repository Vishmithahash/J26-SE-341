/**
 * Component 4 (C4) - Active Project Hook
 * Handles project switching, state isolation, and stale async response prevention.
 * Provides fallback project discovery from projectsApi if context hasn't resolved an active project.
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { useProject } from '../../../context/ProjectContext';
import { useAuth } from '../../../context/AuthContext';
import { projectsApi } from '../../../services/projects';

export function useC4Project(onProjectReset) {
  const {
    activeProject: contextProject,
    activeProjectId: contextProjectId,
    isLoadingActive: contextLoading,
  } = useProject();
  const { user, isAuthenticated } = useAuth();

  const [fallbackProject, setFallbackProject] = useState(null);
  const [isLoadingFallback, setIsLoadingFallback] = useState(false);
  const [availableProjects, setAvailableProjects] = useState([]);

  // Auto-resolve fallback project if context didn't resolve one
  useEffect(() => {
    let isCancelled = false;
    async function loadFallback() {
      if (contextProject || contextProjectId || !isAuthenticated || !user?.id) {
        return;
      }
      setIsLoadingFallback(true);
      try {
        const res = await projectsApi.listProjects({ limit: 20 });
        if (isCancelled) return;
        const items = res?.items || [];
        setAvailableProjects(items);
        const activeOne = items.find((p) => p.lifecycle !== 'archived') || items[0] || null;
        if (activeOne) {
          setFallbackProject(activeOne);
        }
      } catch (err) {
        console.warn('Could not auto-resolve project for C4:', err);
      } finally {
        if (!isCancelled) setIsLoadingFallback(false);
      }
    }
    loadFallback();
    return () => {
      isCancelled = true;
    };
  }, [contextProject, contextProjectId, isAuthenticated, user?.id]);

  const activeProject = contextProject || fallbackProject;
  const activeProjectId = contextProjectId || fallbackProject?.project_id || null;
  const isLoadingActive = contextLoading || (isLoadingFallback && !activeProject);

  const previousProjectIdRef = useRef(activeProjectId);
  const previousUserIdRef = useRef(user?.id);
  const generationRef = useRef(0);

  useEffect(() => {
    const projectChanged = previousProjectIdRef.current !== activeProjectId;
    const userChanged = previousUserIdRef.current !== user?.id;

    if (projectChanged || userChanged) {
      generationRef.current += 1;
      previousProjectIdRef.current = activeProjectId;
      previousUserIdRef.current = user?.id;

      if (typeof onProjectReset === 'function') {
        onProjectReset();
      }
    }
  }, [activeProjectId, user?.id, onProjectReset]);

  const switchProject = useCallback((project) => {
    setFallbackProject(project);
  }, []);

  const getGeneration = () => generationRef.current;
  const isCurrentGeneration = (gen) => gen === generationRef.current;

  return {
    activeProject,
    activeProjectId,
    availableProjects,
    switchProject,
    isLoadingActive,
    isProjectReady: Boolean(activeProjectId && !isLoadingActive),
    getGeneration,
    isCurrentGeneration,
  };
}
