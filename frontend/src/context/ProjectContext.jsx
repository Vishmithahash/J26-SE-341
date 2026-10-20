import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useAuth } from './AuthContext';
import { projectsApi } from '../services/projects';
import {
  getStoredActiveProjectId,
  setStoredActiveProjectId,
  clearStoredActiveProjectId,
} from '../services/activeProject';

const ProjectContext = createContext(null);

export const ProjectProvider = ({ children }) => {
  const { user, isAuthenticated } = useAuth();
  const [activeProject, setActiveProjectState] = useState(null);
  const [isLoadingActive, setIsLoadingActive] = useState(false);

  // Sync and validate active project whenever user identity changes
  const loadActiveProject = useCallback(async () => {
    if (!isAuthenticated || !user?.id) {
      setActiveProjectState(null);
      return;
    }

    const storedId = getStoredActiveProjectId(user.id);
    if (!storedId) {
      setActiveProjectState(null);
      return;
    }

    setIsLoadingActive(true);
    try {
      const res = await projectsApi.getProject(storedId);
      const project = res.project;
      // Requirement: clear or replace selection if project is archived or inaccessible
      if (project && project.lifecycle !== 'archived') {
        setActiveProjectState(project);
      } else {
        clearStoredActiveProjectId(user.id);
        setActiveProjectState(null);
      }
    } catch {
      // Access lost or invalid ID
      clearStoredActiveProjectId(user.id);
      setActiveProjectState(null);
    } finally {
      setIsLoadingActive(false);
    }
  }, [isAuthenticated, user]);

  useEffect(() => {
    loadActiveProject();
  }, [loadActiveProject]);

  const selectActiveProject = async (projectId) => {
    if (!user?.id) return null;
    if (!projectId) {
      clearStoredActiveProjectId(user.id);
      setActiveProjectState(null);
      return null;
    }

    setIsLoadingActive(true);
    try {
      const res = await projectsApi.getProject(projectId);
      const project = res.project;
      if (project.lifecycle === 'archived') {
        throw new Error('Archived projects cannot be set as the active project.');
      }
      setStoredActiveProjectId(user.id, project.project_id);
      setActiveProjectState(project);
      return project;
    } catch (err) {
      clearStoredActiveProjectId(user.id);
      setActiveProjectState(null);
      throw err;
    } finally {
      setIsLoadingActive(false);
    }
  };

  const clearActiveProject = () => {
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
