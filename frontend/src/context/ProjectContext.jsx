import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from './AuthContext';
import { projectsApi } from '../services/projects';
import {
  getStoredActiveProjectId,
  setStoredActiveProjectId,
  clearStoredActiveProjectId,
} from '../services/activeProject';

// Exported pure helpers for response unwrapping and project validation
export const unwrapProjectResponse = (res) => res?.project || res;

export const isValidProject = (proj, expectedId) => {
  return Boolean(
    proj &&
    typeof proj === 'object' &&
    typeof proj.project_id === 'string' &&
    proj.project_id.trim().length > 0 &&
    (expectedId === undefined || proj.project_id === expectedId)
  );
};

export const isSelectableLifecycle = (proj) => {
  return Boolean(proj && proj.lifecycle && proj.lifecycle !== 'archived');
};

const ProjectContext = createContext(null);

export const ProjectProvider = ({ children }) => {
  const { user, isAuthenticated } = useAuth();
  const [activeProject, setActiveProjectState] = useState(null);
  const [isLoadingActive, setIsLoadingActive] = useState(false);

  // Request counter to protect against stale asynchronous responses and account switches
  const requestCounterRef = useRef(0);

  // Sync and validate active project whenever user identity changes
  const loadActiveProject = useCallback(async () => {
    const currentRequestId = ++requestCounterRef.current;
    const currentUserId = user?.id;

    if (!isAuthenticated || !currentUserId) {
      setActiveProjectState(null);
      return;
    }

    const storedId = getStoredActiveProjectId(currentUserId);
    if (!storedId) {
      setActiveProjectState(null);
      return;
    }

    setIsLoadingActive(true);
    try {
      const res = await projectsApi.getProject(storedId);
      // Support both direct ProjectResponse and wrapped { project: ... }
      const project = res?.project || res;

      // Ensure response is for the latest attempt and current user
      if (requestCounterRef.current !== currentRequestId || user?.id !== currentUserId) {
        return;
      }

      if (isValidProject(project, storedId) && isSelectableLifecycle(project)) {
        setActiveProjectState(project);
      } else {
        clearStoredActiveProjectId(currentUserId);
        setActiveProjectState(null);
      }
    } catch {
      // Inaccessible, deleted, or network error
      if (requestCounterRef.current === currentRequestId && user?.id === currentUserId) {
        clearStoredActiveProjectId(currentUserId);
        setActiveProjectState(null);
      }
    } finally {
      if (requestCounterRef.current === currentRequestId && user?.id === currentUserId) {
        setIsLoadingActive(false);
      }
    }
  }, [isAuthenticated, user]);

  useEffect(() => {
    loadActiveProject();
  }, [loadActiveProject]);

  const selectActiveProject = async (projectId) => {
    const currentRequestId = ++requestCounterRef.current;
    const currentUserId = user?.id;

    if (!currentUserId) return null;
    if (!projectId || typeof projectId !== 'string' || !projectId.trim()) {
      clearStoredActiveProjectId(currentUserId);
      setActiveProjectState(null);
      return null;
    }

    const targetId = projectId.trim();
    setIsLoadingActive(true);
    try {
      const res = await projectsApi.getProject(targetId);
      // Support both direct ProjectResponse and wrapped { project: ... }
      const project = res?.project || res;

      if (requestCounterRef.current !== currentRequestId || user?.id !== currentUserId) {
        return null;
      }

      if (!isValidProject(project, targetId)) {
        throw new Error('Received invalid project response from server.');
      }

      if (!isSelectableLifecycle(project)) {
        throw new Error('Archived projects cannot be set as the active project.');
      }

      setStoredActiveProjectId(currentUserId, project.project_id);
      setActiveProjectState(project);
      return project;
    } catch (err) {
      if (requestCounterRef.current === currentRequestId && user?.id === currentUserId) {
        clearStoredActiveProjectId(currentUserId);
        setActiveProjectState(null);
      }
      throw err;
    } finally {
      if (requestCounterRef.current === currentRequestId && user?.id === currentUserId) {
        setIsLoadingActive(false);
      }
    }
  };

  const clearActiveProject = () => {
    requestCounterRef.current += 1;
    if (user?.id) {
      clearStoredActiveProjectId(user.id);
    }
    setActiveProjectState(null);
  };

  return (
    <ProjectContext.Provider
      value={{
        activeProject,
        activeProjectId: activeProject?.project_id || null,
        isLoadingActive,
        selectActiveProject,
        clearActiveProject,
        refreshActiveProject: loadActiveProject,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
};

export const useProject = () => {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error('useProject must be used within a ProjectProvider');
  }
  return context;
};

