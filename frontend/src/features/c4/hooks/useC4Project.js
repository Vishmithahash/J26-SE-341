/**
 * Component 4 (C4) - Authoritative Active Project Hook
 * Strictly consumes the shared activeProject and activeProjectId from ProjectContext.
 * Selection delegates exclusively to the shared selectActiveProject service.
 * Eliminates silent auto-discovery fallbacks and cross-account project leakage.
 * Tracks generation counters to invalidate stale asynchronous responses on project/account changes.
 */

import { useRef, useEffect, useCallback, useState } from 'react';
import { useProject } from '../../../context/ProjectContext';
import { useAuth } from '../../../context/AuthContext';
import { projectsApi } from '../../../services/projects';

export function useC4Project(onProjectReset) {
  const {
    activeProject,
    activeProjectId,
    isLoadingActive,
    selectActiveProject,
  } = useProject();
  const { user, isAuthenticated } = useAuth();

  const [availableProjects, setAvailableProjects] = useState([]);
  const [isLoadingAvailable, setIsLoadingAvailable] = useState(false);

  // Load authorized projects list purely for selection picker dropdown options (no auto-selection)
  useEffect(() => {
    let isCancelled = false;
    async function loadOptions() {
      if (!isAuthenticated || !user?.id) {
        setAvailableProjects([]);
        return;
      }
      setIsLoadingAvailable(true);
      try {
        const res = await projectsApi.listProjects({ limit: 50 });
        if (isCancelled) return;
        const items = res?.items || [];
        setAvailableProjects(items.filter((p) => p.lifecycle !== 'archived'));
      } catch {
        if (!isCancelled) setAvailableProjects([]);
      } finally {
        if (!isCancelled) setIsLoadingAvailable(false);
      }
    }
    loadOptions();
    return () => {
      isCancelled = true;
    };
  }, [isAuthenticated, user?.id]);

  const previousProjectIdRef = useRef(activeProjectId);
  const previousUserIdRef = useRef(user?.id);
  const generationRef = useRef(0);

  // Invalidate in-flight reads, clear modals and selection states on project or account transitions
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

  // Project selection delegates strictly to shared ProjectContext authority
  const switchProject = useCallback(
    async (projectOrId) => {
      const pid = typeof projectOrId === 'string' ? projectOrId : projectOrId?.project_id;
      if (!pid || typeof selectActiveProject !== 'function') return;
      await selectActiveProject(pid);
    },
    [selectActiveProject]
  );

  const getGeneration = () => generationRef.current;
  const isCurrentGeneration = (gen) => gen === generationRef.current;

  return {
    activeProject: activeProject || null,
    activeProjectId: activeProjectId || null,
    availableProjects,
    isLoadingAvailable,
    switchProject,
    isLoadingActive: Boolean(isLoadingActive),
    isProjectReady: Boolean(activeProjectId && !isLoadingActive),
    getGeneration,
    isCurrentGeneration,
  };
}
