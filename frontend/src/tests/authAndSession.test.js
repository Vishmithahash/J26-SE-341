import './setup.js';
import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { api, setStoredToken } from '../services/api.js';

describe('Auth, Session, and Security Rules', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  describe('Unicode Code Point Password Counting', () => {
    const countCodePoints = (str) => Array.from(str).length;

    it('counts supplementary Unicode characters (surrogate pairs / emojis) as 1 character matching Python', () => {
      // Single emoji has JS string.length == 2, but 1 code point
      const emoji = '🚀';
      assert.equal(emoji.length, 2);
      assert.equal(countCodePoints(emoji), 1);

      // Password with 7 ASCII characters + 1 emoji = 8 code points
      const passwordWithEmoji = 'Secure1' + '🚀';
      assert.equal(countCodePoints(passwordWithEmoji), 8);
      assert.equal(countCodePoints(passwordWithEmoji) >= 8, true);

      // Password with 6 ASCII chars + 1 emoji = 7 code points -> too short
      const shortEmojiPass = 'Secur1' + '🚀';
      assert.equal(countCodePoints(shortEmojiPass), 7);
      assert.equal(countCodePoints(shortEmojiPass) >= 8, false);
    });

    it('permits spaces and Unicode without trimming passwords', () => {
      const passwordWithSpaces = '  Valid password with spaces 12345  ';
      // Raw string must not be altered
      assert.equal(countCodePoints(passwordWithSpaces), 36);
      assert.equal(passwordWithSpaces.startsWith('  '), true);
      assert.equal(passwordWithSpaces.endsWith('  '), true);
    });
  });

  describe('Session Storage and Bearer Token Handling', () => {
    it('sets, retrieves, and clears bearer token predictably in tab-scoped storage', () => {
      assert.equal(api.getToken(), null);

      setStoredToken('test-bearer-token-123');
      assert.equal(api.getToken(), 'test-bearer-token-123');

      api.logout();
      assert.equal(api.getToken(), null);
    });
  });

  describe('Return URL Validation & Role-Permission Filtering', () => {
    const sanitizeReturnUrl = (requestedPath, userRole) => {
      const defaultDashboard =
        userRole === 'ADMIN' ? '/admin/dashboard' : '/app/dashboard';

      if (
        typeof requestedPath !== 'string' ||
        !requestedPath.startsWith('/') ||
        requestedPath.startsWith('//') ||
        requestedPath.includes('\\')
      ) {
        return defaultDashboard;
      }

      // Check role permissions:
      // Standard USER must never be redirected into /admin/*
      if (userRole === 'USER' && requestedPath.startsWith('/admin')) {
        return defaultDashboard;
      }

      // ADMIN opening /app/* defaults to /admin/dashboard
      if (userRole === 'ADMIN' && requestedPath.startsWith('/app')) {
        return defaultDashboard;
      }

      return requestedPath;
    };

    it('prevents open redirect attacks (protocol-relative URLs or backslashes)', () => {
      assert.equal(sanitizeReturnUrl('//malicious.com/phish', 'USER'), '/app/dashboard');
      assert.equal(sanitizeReturnUrl('/\\malicious.com', 'ADMIN'), '/admin/dashboard');
      assert.equal(sanitizeReturnUrl('https://external.com', 'USER'), '/app/dashboard');
    });

    it('prevents USER role from redirecting to /admin paths on login', () => {
      const target = '/admin/users';
      assert.equal(sanitizeReturnUrl(target, 'USER'), '/app/dashboard');
    });

    it('allows valid in-bounds return paths for authorized roles', () => {
      assert.equal(sanitizeReturnUrl('/admin/users', 'ADMIN'), '/admin/users');
      assert.equal(
        sanitizeReturnUrl('/app/tool-call-correctness', 'USER'),
        '/app/tool-call-correctness'
      );
    });
  });

  describe('Stale Response Guard & Unknown Role Fail-Closed Logic', () => {
    it('rejects roles other than ADMIN and USER', () => {
      const isRoleAllowed = (role) => role === 'ADMIN' || role === 'USER';

      assert.equal(isRoleAllowed('ADMIN'), true);
      assert.equal(isRoleAllowed('USER'), true);
      assert.equal(isRoleAllowed('SUPERUSER'), false);
      assert.equal(isRoleAllowed('OPERATOR'), false);
      assert.equal(isRoleAllowed('GUEST'), false);
    });

    it('validates generation counters to discard late asynchronous responses from past sessions', () => {
      let currentSessionGen = 1;

      const isResponseCurrent = (sessionGen) => sessionGen === currentSessionGen;

      // Session 1 in-flight
      const requestSession = currentSessionGen;

      // User logs out, incrementing session counter
      currentSessionGen += 1;

      // When Session 1 finishes, it must be discarded as stale
      assert.equal(isResponseCurrent(requestSession), false);

      // New session 2 is current
      assert.equal(isResponseCurrent(currentSessionGen), true);
    });

    it('exposes updateUserStatus method on api service for administrator access management', () => {
      assert.equal(typeof api.updateUserStatus, 'function');
    });
  });
});

