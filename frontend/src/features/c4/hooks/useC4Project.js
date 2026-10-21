/**
 * Component 4 (C4) - Active Project Hook
 * Handles project switching, state isolation, and stale async response prevention.
 */

import { useRef, useEffect } from 'react';
import { useProject } from '../../../context/ProjectContext';
import { useAuth } from '../../../context/AuthContext';

export function useC4Project(onProjectReset) {
  const { activeProject, activeProjectId, isLoadingActive } = useProject();
  const { user } = useAuth();
  const previousProjectIdRef = useRef(activeProjectId);
  const previousUserIdRef = useRef(user?.id);
  const generationRef = useRef(0);

  useEffect(() => {
    const projectChanged = previousProjectIdRef.current !== activeProjectId;
    const userChanged = previousUserIdRef.current !== user?.id;

    if (projectChanged || userChanged) {
      // Increment request generation counter to invalidate all pending async callbacks
      generationRef.current += 1;
      previousProjectIdRef.current = activeProjectId;
      previousUserIdRef.current = user?.id;

      if (typeof onProjectReset === 'function') {
        onProjectReset();
      }
    }
  }, [activeProjectId, user?.id, onProjectReset]);

  /**
   * Helper to ensure an async operation response belongs to the current project and session.
   * Usage:
   * const gen = getGeneration();
   * const res = await c4Api...;
   * if (!isCurrentGeneration(gen)) return; // stale response discarded
   */
  const getGeneration = () => generationRef.current;
  const isCurrentGeneration = (gen) => gen === generationRef.current;

  return {
    activeProject,
    activeProjectId,
    isLoadingActive,
    isProjectReady: Boolean(activeProjectId && !isLoadingActive),
    getGeneration,
    isCurrentGeneration,
  };
}
