import './setup.js';
import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

import { api, setStoredToken, setOnUnauthorizedCallback, ApiError } from '../services/api.js';
import { integrationApi } from '../features/integration/integrationApi.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

describe('Shared Frontend Corrections Regression Suite', () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    setStoredToken(null);
  });

  describe('1. AuthContext and ProjectContext Restoration Contracts', () => {
    it('AuthContext exposes isAuthenticated derived from user and token', () => {
      const authContextPath = path.resolve(__dirname, '../context/AuthContext.jsx');
      const content = fs.readFileSync(authContextPath, 'utf8');

      // Verify isAuthenticated is exported in the context value
      assert.match(
        content,
        /isAuthenticated:\s*Boolean\(user\s*&&\s*token\)/,
        'AuthContext must expose isAuthenticated: Boolean(user && token)'
      );
    });

    it('ProjectContext awaits isAuthLoading before deciding project availability and restores saved active project', () => {
      const projContextPath = path.resolve(__dirname, '../context/ProjectContext.jsx');
      const content = fs.readFileSync(projContextPath, 'utf8');

      // Verify ProjectContext consumes isAuthenticated and isLoading: isAuthLoading from useAuth
      assert.match(
        content,
        /const\s*\{[^}]*user[^}]*isAuthenticated[^}]*isLoading:\s*isAuthLoading[^}]*\}\s*=\s*useAuth\(\)/,
        'ProjectContext must consume isAuthenticated and isAuthLoading'
      );

      // Verify ProjectContext waits for isAuthLoading to complete
      assert.match(
        content,
        /if\s*\(\s*isAuthLoading\s*\)\s*\{[\s\S]*?return;[\s\S]*?\}/,
        'ProjectContext must wait for authentication initialization'
      );

      // Verify ProjectContext clears active project when not authenticated
      assert.match(
        content,
        /if\s*\(\s*!isAuthenticated\s*\|\|\s*!currentUserId\s*\)/,
        'ProjectContext must clear active project state on logout or account change'
      );

      // Verify ProjectContext discards stale responses using a request generation counter
      assert.match(
        content,
        /requestCounterRef\.current/,
        'ProjectContext must track requestCounterRef to discard stale responses'
      );
    });
  });

  describe('2. C2 Publication Receipts and Attribution Isolation', () => {
    it('RunReportModal only displays publication receipt for matching evaluation_id', () => {
      const modalPath = path.resolve(__dirname, '../features/c2/components/RunReportModal.jsx');
      const content = fs.readFileSync(modalPath, 'utf8');

      // Verify receipt check binds to report.evaluation_id
      assert.match(
        content,
        /lastConfirmedReceipt\.evaluation_id\s*===\s*report\.evaluation_id/,
        'RunReportModal must only mark evaluation as published if lastConfirmedReceipt.evaluation_id matches report.evaluation_id'
      );
    });

    it('useC2Results scopes publication state and receipts strictly to evaluation identity', () => {
      const hookPath = path.resolve(__dirname, '../features/c2/hooks/useC2Results.js');
      const content = fs.readFileSync(hookPath, 'utf8');

      // Verify receipt storage is scoped per evaluation ID
      assert.match(
        content,
        /receiptsByEvalRef/,
        'useC2Results must store receipts per evaluation ID'
      );

      // Verify late publication responses belonging to an older evaluation are ignored
      assert.match(
        content,
        /selectedEvalIdRef\.current\s*===\s*targetEvalId/,
        'useC2Results must only apply publication state if user is still on the target evaluation'
      );
    });
  });

  describe('3. Authenticated Download Session Expiry and Token Protection', () => {
    it('downloadFile handles HTTP 401 by clearing session and invoking onUnauthorized', async () => {
      let unauthorizedCalled = false;
      setOnUnauthorizedCallback(() => {
        unauthorizedCalled = true;
      });

      setStoredToken('expired-mock-token');
      assert.equal(api.getToken(), 'expired-mock-token');

      // Mock fetch returning HTTP 401 Unauthorized
      globalThis.fetch = async () => ({
        ok: false,
        status: 401,
        headers: new Headers({ 'content-type': 'application/json' }),
        text: async () => JSON.stringify({ detail: 'Session expired or invalid credentials' }),
      });

      try {
        await api.downloadFile('/api/v1/projects/proj-1/integration/plans/p-1/executions/e-1/report/export?format=json');
        assert.fail('downloadFile should have thrown an ApiError on 401');
      } catch (err) {
        assert.ok(err instanceof ApiError);
        assert.equal(err.status, 401);
        assert.match(err.message, /Session expired/);
      }

      // Verify session token was cleared and unauthorized callback invoked
      assert.equal(api.getToken(), null);
      assert.equal(unauthorizedCalled, true);

      setOnUnauthorizedCallback(null);
    });

    it('exportReportFile keeps bearer tokens out of URL and in Authorization header', async () => {
      let requestedUrl = null;
      let requestedHeaders = null;

      globalThis.fetch = async (url, opts) => {
        requestedUrl = url;
        requestedHeaders = opts?.headers || {};
        return {
          ok: true,
          status: 200,
          headers: new Headers({
            'content-disposition': 'attachment; filename="report_exec-99.json"',
          }),
          blob: async () => new Blob(['{}'], { type: 'application/json' }),
        };
      };

      globalThis.document = {
        body: {
          appendChild: () => {},
          removeChild: () => {},
        },
        createElement: () => ({
          click: () => {},
          href: '',
          download: '',
        }),
      };
      globalThis.URL = {
        createObjectURL: () => 'blob:mock-url',
        revokeObjectURL: () => {},
      };

      setStoredToken('secret-bearer-token-xyz');
      const res = await integrationApi.exportReportFile('proj-abc', 'plan-1', 'exec-99', 'json');

      assert.equal(res.filename, 'report_exec-99.json');
      assert.equal(requestedHeaders['Authorization'], 'Bearer secret-bearer-token-xyz');
      assert.doesNotMatch(requestedUrl, /secret-bearer-token-xyz/);
      assert.doesNotMatch(requestedUrl, /token=/i);
    });
  });

  describe('4. Error State Accuracy in Shared Results View', () => {
    it('CombinedResultsView differentiates network/server failure from genuine empty plans and executions', () => {
      const viewPath = path.resolve(__dirname, '../features/integration/CombinedResultsView.jsx');
      const content = fs.readFileSync(viewPath, 'utf8');

      // Verify plans failed state vs genuine empty state
      assert.match(
        content,
        /error\s*&&\s*plans\.length\s*===\s*0/,
        'CombinedResultsView must check for error condition when plans list is empty'
      );
      assert.match(
        content,
        /Failed to Load Integration Results/,
        'CombinedResultsView must show explicit failure card instead of claiming no plans exist'
      );
      assert.match(
        content,
        /No Shared Integration Plans Found/,
        'CombinedResultsView preserves genuine empty state card only when request succeeded with 0 plans'
      );

      // Verify executions failed state vs genuine empty state
      assert.match(
        content,
        /error\s*&&\s*executions\.length\s*===\s*0/,
        'CombinedResultsView must check for error condition when executions list is empty'
      );
      assert.match(
        content,
        /Unable to load plan executions/,
        'CombinedResultsView must display error card when executions fetch fails'
      );
      assert.match(
        content,
        /No executions recorded for this plan yet/,
        'CombinedResultsView preserves genuine empty state card when plan has no executions'
      );
    });
  });
});
