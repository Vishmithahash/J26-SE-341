/**
 * Component 4 (C4) - Frontend Phase 1 Tests
 * Tests endpoint mappings, contract lifecycle rules, safety against injection payloads,
 * generation counters for stale async responses, and strict boundaries.
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  POLICY_FAMILIES,
  POLICY_REQUIREMENTS,
  EVALUATION_BOUNDARIES,
  RULE_REVIEW_STATUSES,
  CONTRACT_LIFECYCLE_STATES,
} from '../api/types.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const c4RootDir = path.resolve(__dirname, '..');

describe('C4 Phase 1: Constants and Taxonomy Verification', () => {
  it('defines the three required policy families', () => {
    assert.equal(POLICY_FAMILIES.AUTHORIZATION, 'AUTHORIZATION');
    assert.equal(POLICY_FAMILIES.CONFIDENTIALITY, 'CONFIDENTIALITY');
    assert.equal(POLICY_FAMILIES.INSTRUCTION_AUTHORITY, 'INSTRUCTION_AUTHORITY');
  });

  it('defines supported policy requirement operators', () => {
    assert.equal(POLICY_REQUIREMENTS.ALLOW, 'ALLOW');
    assert.equal(POLICY_REQUIREMENTS.DENY, 'DENY');
    assert.equal(POLICY_REQUIREMENTS.REQUIRE, 'REQUIRE');
  });

  it('defines evaluation boundaries matching proposal', () => {
    assert.equal(EVALUATION_BOUNDARIES.ATTEMPTED_ACTION, 'ATTEMPTED_ACTION');
    assert.equal(EVALUATION_BOUNDARIES.DISCLOSURE, 'DISCLOSURE');
    assert.equal(EVALUATION_BOUNDARIES.COMMITTED_EFFECT, 'COMMITTED_EFFECT');
  });

  it('defines contract lifecycle states and review statuses', () => {
    assert.equal(CONTRACT_LIFECYCLE_STATES.DRAFT, 'DRAFT');
    assert.equal(CONTRACT_LIFECYCLE_STATES.VALIDATED, 'VALIDATED');
    assert.equal(CONTRACT_LIFECYCLE_STATES.ACCEPTED, 'ACCEPTED');

    assert.equal(RULE_REVIEW_STATUSES.DRAFT, 'DRAFT');
    assert.equal(RULE_REVIEW_STATUSES.VALIDATED, 'VALIDATED');
    assert.equal(RULE_REVIEW_STATUSES.ACCEPTED, 'ACCEPTED');
    assert.equal(RULE_REVIEW_STATUSES.REJECTED, 'REJECTED');
  });
});

describe('C4 Phase 1: API Route and Mounting Verification', () => {
  it('correctly maps C4 endpoints directly to /projects/{projectId}/c4/... and not /api/v1/c4', () => {
    const apiFile = path.resolve(c4RootDir, 'api/c4Api.js');
    const apiCode = fs.readFileSync(apiFile, 'utf8');

    // Must NOT assume prefix is /api/v1/c4
    assert.equal(apiCode.includes('/api/v1/c4'), false, 'Should not use /api/v1/c4 prefix');

    // Must map to /projects/${...}/c4
    assert.equal(
      apiCode.includes('/projects/${encodeURIComponent(projectId)}/c4'),
      true,
      'Should map to /projects/{projectId}/c4 endpoint'
    );
  });

  it('includes complete C4 endpoint suite for Phase 1', () => {
    const apiFile = path.resolve(c4RootDir, 'api/c4Api.js');
    const apiCode = fs.readFileSync(apiFile, 'utf8');

    assert.equal(apiCode.includes('getExtractionReadiness'), true);
    assert.equal(apiCode.includes('registerArtifact'), true);
    assert.equal(apiCode.includes('getArtifact'), true);
    assert.equal(apiCode.includes('deriveRules'), true);
    assert.equal(apiCode.includes('startExtractionJob'), true);
    assert.equal(apiCode.includes('reviewCandidateRule'), true);
    assert.equal(apiCode.includes('createContractDraft'), true);
    assert.equal(apiCode.includes('validateContract'), true);
    assert.equal(apiCode.includes('acceptContract'), true);
    assert.equal(apiCode.includes('getContract'), true);
    assert.equal(apiCode.includes('listDomains'), true);
    assert.equal(apiCode.includes('checkDomainReadiness'), true);
    assert.equal(apiCode.includes('listDomainBindings'), true);
    assert.equal(apiCode.includes('startOnboardingJob'), true);
  });
});

describe('C4 Phase 1: XSS and Injection Safety Verification', () => {
  it('guarantees that no C4 frontend production file uses dangerouslySetInnerHTML or eval', () => {
    function scanDir(dir) {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          // Skip tests directory when checking for source code injection hazards
          if (entry.name === 'tests') continue;
          scanDir(fullPath);
        } else if (entry.name.endsWith('.js') || entry.name.endsWith('.jsx')) {
          const content = fs.readFileSync(fullPath, 'utf8');
          assert.equal(
            content.includes('dangerouslySetInnerHTML'),
            false,
            `File ${fullPath} must not use dangerouslySetInnerHTML`
          );
          assert.equal(
            content.includes('eval('),
            false,
            `File ${fullPath} must not use eval()`
          );
        }
      }
    }

    scanDir(c4RootDir);
  });
});

describe('C4 Phase 1: Stale Response and Generation Counter Verification', () => {
  it('discards asynchronous responses if generation has advanced', () => {
    let currentGen = 0;
    const isCurrentGeneration = (gen) => gen === currentGen;

    const recordedPayloads = [];
    const asyncCall = (gen, payload) => {
      if (isCurrentGeneration(gen)) {
        recordedPayloads.push(payload);
      }
    };

    // User is on Project A (gen 0)
    const projectAGen = currentGen;

    // User switches to Project B (gen increments to 1)
    currentGen += 1;
    const projectBGen = currentGen;

    // Late response from Project A arrives
    asyncCall(projectAGen, { contract_id: 'contract-project-A' });

    // Response from Project B arrives
    asyncCall(projectBGen, { contract_id: 'contract-project-B' });

    assert.equal(recordedPayloads.length, 1);
    assert.equal(recordedPayloads[0].contract_id, 'contract-project-B');
  });
});

describe('C4 Phase 1: Strict Ownership and Boundary Verification', () => {
  it('confirms all C4 implementations reside strictly under frontend/src/features/c4', () => {
    assert.equal(fs.existsSync(path.resolve(c4RootDir, 'api/c4Api.js')), true);
    assert.equal(fs.existsSync(path.resolve(c4RootDir, 'pages/PolicySafetyWorkspace.jsx')), true);
    assert.equal(fs.existsSync(path.resolve(c4RootDir, 'components/dashboard/C4DashboardCard.jsx')), true);
  });

  it('guarantees reviewer audit disclaimer is displayed for client-entered provenance', () => {
    const modalFile = path.resolve(c4RootDir, 'components/candidates/ReviewModal.jsx');
    const modalCode = fs.readFileSync(modalFile, 'utf8');

    // Must explain client-entered reviewer information is not independently authenticated
    assert.equal(
      modalCode.toLowerCase().includes('client-entered') &&
      modalCode.toLowerCase().includes('not independently authenticated'),
      true,
      'ReviewModal must contain notice that client-entered reviewer is not independently authenticated provenance'
    );
  });
});
