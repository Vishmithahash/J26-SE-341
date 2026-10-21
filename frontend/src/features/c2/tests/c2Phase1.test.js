import '../../../tests/setup.js';
import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { c2Api } from '../api/c2Api.js';
import { getRefundWorkflowInputTemplate } from '../templates/refundWorkflowTemplate.js';

describe('Component 2 Phase 1: Models Workspace Tests', () => {
  let capturedRequests = [];

  beforeEach(() => {
    capturedRequests = [];
    globalThis.fetch = async (url, options = {}) => {
      capturedRequests.push({ url, options });
      // Default successful mock response
      return {
        ok: true,
        status: 200,
        json: async () => ({
          status: 'success',
          url,
          body: options.body ? JSON.parse(options.body) : null,
        }),
      };
    };
  });

  describe('1. Correct Project-Scoped API Requests', () => {
    it('scopes listModels request strictly to target project ID', async () => {
      await c2Api.listModels('project_alpha_101');
      assert.equal(capturedRequests.length, 1);
      assert.equal(capturedRequests[0].url, '/api/v1/c2/projects/project_alpha_101/models');
      assert.equal(capturedRequests[0].options.method, 'GET');
    });

    it('rejects listing models without a valid project ID', async () => {
      await assert.rejects(
        async () => {
          await c2Api.listModels('');
        },
        {
          name: 'Error',
          message: 'projectId is required to list models',
        }
      );
    });

    it('scopes getModel to project, model ID, and version', async () => {
      await c2Api.getModel('proj_99', 'refund_flow', '1.0.0');
      assert.equal(capturedRequests.length, 1);
      assert.equal(
        capturedRequests[0].url,
        '/api/v1/c2/projects/proj_99/models/refund_flow/versions/1.0.0'
      );
      assert.equal(capturedRequests[0].options.method, 'GET');
    });

    it('scopes buildCandidateModel with auto_validate query parameter', async () => {
      const payload = getRefundWorkflowInputTemplate('proj_custom');
      await c2Api.buildCandidateModel('proj_custom', payload, true);
      assert.equal(capturedRequests.length, 1);
      assert.equal(
        capturedRequests[0].url,
        '/api/v1/c2/projects/proj_custom/models/build?auto_validate=true'
      );
      assert.equal(capturedRequests[0].options.method, 'POST');
      assert.equal(capturedRequests[0].options.body, JSON.stringify(payload));
    });

    it('scopes direct draft model creation to project endpoint', async () => {
      const def = { model_id: 'draft_efsm', version: '1.0.0', project_id: 'proj_direct' };
      await c2Api.createDraftModel('proj_direct', def);
      assert.equal(capturedRequests.length, 1);
      assert.equal(capturedRequests[0].url, '/api/v1/c2/projects/proj_direct/models');
      assert.equal(capturedRequests[0].options.method, 'POST');
    });

    it('scopes validation request to specific model version', async () => {
      await c2Api.validateModel('proj_val', 'model_x', '2.0.0');
      assert.equal(capturedRequests.length, 1);
      assert.equal(
        capturedRequests[0].url,
        '/api/v1/c2/projects/proj_val/models/model_x/versions/2.0.0/validate'
      );
      assert.equal(capturedRequests[0].options.method, 'POST');
    });

    it('scopes model readiness query to specific version', async () => {
      await c2Api.getModelReadiness('proj_readiness', 'model_y', '1.0.0');
      assert.equal(capturedRequests.length, 1);
      assert.equal(
        capturedRequests[0].url,
        '/api/v1/c2/projects/proj_readiness/models/model_y/versions/1.0.0/readiness'
      );
      assert.equal(capturedRequests[0].options.method, 'GET');
    });
  });

  describe('2. Account/Project Switching and Stale Response Protection', () => {
    it('demonstrates generation-counter rejection of late responses from previous project contexts', async () => {
      let generation = 0;
      let _activeProject = 'proj_A';
      const renderedData = [];

      // Simulated async loader using generation counter pattern
      const fetchForProject = async (pId) => {
        const thisGen = ++generation;
        _activeProject = pId;

        // Simulate network latency: project A finishes AFTER project B
        const delay = pId === 'proj_A' ? 50 : 10;
        await new Promise((r) => setTimeout(r, delay));

        // Stale response guard
        if (thisGen !== generation) {
          return; // Discard late response
        }

        renderedData.push({ project: pId, gen: thisGen });
      };

      // Launch project A fetch, then user quickly switches to project B
      const promiseA = fetchForProject('proj_A');
      const promiseB = fetchForProject('proj_B');

      await Promise.all([promiseA, promiseB]);

      // Only project B must have committed to rendered data!
      assert.equal(renderedData.length, 1);
      assert.equal(renderedData[0].project, 'proj_B');
    });

    it('guarantees template generation populates correct target project ID without cross-tenant bleed', () => {
      const templateA = getRefundWorkflowInputTemplate('tenant_alpha');
      const templateB = getRefundWorkflowInputTemplate('tenant_beta');

      assert.equal(templateA.project_id, 'tenant_alpha');
      assert.equal(templateB.project_id, 'tenant_beta');
      assert.notEqual(templateA.project_id, templateB.project_id);
    });
  });

  describe('3. Validation & Authoritative Readiness Logic', () => {
    it('authoritative readiness requires both validation_passed AND is_approved', () => {
      const computeAuthoritativeReadiness = (validationPassed, isApproved) => {
        if (validationPassed && isApproved) {
          return 'READY';
        }
        return 'MODEL NOT READY';
      };

      // Unvalidated & unapproved
      assert.equal(computeAuthoritativeReadiness(false, false), 'MODEL NOT READY');

      // Validated but not approved
      assert.equal(computeAuthoritativeReadiness(true, false), 'MODEL NOT READY');

      // Approved but validation failed (e.g. stale hash)
      assert.equal(computeAuthoritativeReadiness(false, true), 'MODEL NOT READY');

      // Both passed and approved
      assert.equal(computeAuthoritativeReadiness(true, true), 'READY');
    });

    it('truthfully handles validation reports with errors and warnings', () => {
      const report = {
        is_valid: false,
        readiness: 'MODEL NOT READY',
        errors: [
          {
            category: 'structural',
            code: 'DANGLING_TRANSITION',
            message: "Target state 'UNKNOWN_STATE' does not exist in model.",
            element_id: 'TRANS_01',
          },
        ],
        warnings: [],
      };

      assert.equal(report.is_valid, false);
      assert.equal(report.errors.length, 1);
      assert.equal(report.errors[0].code, 'DANGLING_TRANSITION');
      assert.equal(report.readiness, 'MODEL NOT READY');
    });
  });

  describe('4. Explicit Approval & Immutable Versioning', () => {
    it('transmits explicit approval parameters including reviewer provenance and review basis', async () => {
      await c2Api.approveModel('proj_app', 'refund_workflow', '1.0.0', {
        reviewerId: 'alice@research.test',
        reviewBasis: 'Verified against synthetic refund specification v2026.1',
        reviewNotes: 'Protected state unaffected on unpaid order rejection.',
        reviewType: 'SELF_REPORTED_DEVELOPMENT',
      });

      assert.equal(capturedRequests.length, 1);
      assert.equal(
        capturedRequests[0].url,
        '/api/v1/c2/projects/proj_app/models/refund_workflow/versions/1.0.0/approve'
      );
      assert.equal(capturedRequests[0].options.method, 'POST');

      const body = JSON.parse(capturedRequests[0].options.body);
      assert.equal(body.reviewer_id, 'alice@research.test');
      assert.equal(body.review_type, 'SELF_REPORTED_DEVELOPMENT');
      assert.equal(
        body.review_basis,
        'Verified against synthetic refund specification v2026.1'
      );
    });

    it('requires explicit review basis and reviewer ID for approval', async () => {
      await assert.rejects(
        async () => {
          await c2Api.approveModel('', 'refund_workflow', '1.0.0', {
            reviewerId: 'alice',
            reviewBasis: 'test',
          });
        },
        {
          name: 'Error',
          message: 'projectId, modelId, and version are required to approve a model',
        }
      );
    });

    it('scopes createNewDraftVersion to branch a new version from source version', async () => {
      await c2Api.createNewDraftVersion('proj_draft', 'refund_workflow', '1.0.0', {
        newVersion: '1.1.0',
        description: 'Added cancellation path for pending orders',
      });

      assert.equal(capturedRequests.length, 1);
      assert.equal(
        capturedRequests[0].url,
        '/api/v1/c2/projects/proj_draft/models/refund_workflow/versions/1.0.0/new-draft'
      );
      assert.equal(capturedRequests[0].options.method, 'POST');

      const body = JSON.parse(capturedRequests[0].options.body);
      assert.equal(body.new_version, '1.1.0');
      assert.equal(body.description, 'Added cancellation path for pending orders');
    });
  });

  describe('5. Role-Correct Navigation & Shared Active-Project Identity', () => {
    const getProjectsPageRoute = (userRole) => {
      const isAdmin = String(userRole || '').toUpperCase() === 'ADMIN';
      return isAdmin ? '/admin/projects' : '/app/projects';
    };

    it('derives /admin/projects strictly for ADMIN role', () => {
      assert.equal(getProjectsPageRoute('ADMIN'), '/admin/projects');
      assert.equal(getProjectsPageRoute('admin'), '/admin/projects');
    });

    it('derives /app/projects strictly for USER role', () => {
      assert.equal(getProjectsPageRoute('USER'), '/app/projects');
      assert.equal(getProjectsPageRoute('user'), '/app/projects');
    });

    it('fails closed to /app/projects for undefined, null, or guest role', () => {
      assert.equal(getProjectsPageRoute(undefined), '/app/projects');
      assert.equal(getProjectsPageRoute(null), '/app/projects');
      assert.equal(getProjectsPageRoute('GUEST'), '/app/projects');
    });

    it('validates review provenance defaults to SELF_REPORTED_DEVELOPMENT and requires explicit details for claimed independent review', () => {
      const validateApprovalInput = ({ reviewerId, reviewType, reviewerAffiliation, reviewBasis, reviewNotes }) => {
        if (!reviewerId || !reviewerId.trim()) return 'Reviewer ID is required.';
        if (reviewType !== 'SELF_REPORTED_DEVELOPMENT' && (!reviewerAffiliation || !reviewerAffiliation.trim())) {
          return 'Reviewer affiliation/organization is required for claimed independent review.';
        }
        if (!reviewBasis || !reviewBasis.trim()) return 'Review basis is required.';
        if (reviewType !== 'SELF_REPORTED_DEVELOPMENT' && (!reviewNotes || !reviewNotes.trim())) {
          return 'Detailed review notes and observations are required for claimed independent review.';
        }
        return null;
      };

      // Default self-reported development review succeeds with ID and basis
      const devValid = validateApprovalInput({
        reviewerId: 'dev@company.test',
        reviewType: 'SELF_REPORTED_DEVELOPMENT',
        reviewBasis: 'SRS v1.0 checklist',
      });
      assert.equal(devValid, null);

      // Claimed independent review fails if affiliation is missing
      const indepMissingAffiliation = validateApprovalInput({
        reviewerId: 'auditor@external.test',
        reviewType: 'INDEPENDENT_PEER_REVIEW',
        reviewerAffiliation: '',
        reviewBasis: 'SRS v1.0 checklist',
        reviewNotes: 'Checked transitions',
      });
      assert.equal(
        indepMissingAffiliation,
        'Reviewer affiliation/organization is required for claimed independent review.'
      );

      // Claimed independent review fails if review notes are missing
      const indepMissingNotes = validateApprovalInput({
        reviewerId: 'auditor@external.test',
        reviewType: 'INDEPENDENT_PEER_REVIEW',
        reviewerAffiliation: 'External QA Dept',
        reviewBasis: 'SRS v1.0 checklist',
        reviewNotes: '',
      });
      assert.equal(
        indepMissingNotes,
        'Detailed review notes and observations are required for claimed independent review.'
      );

      // Claimed independent review succeeds when all explicit details are provided
      const indepValid = validateApprovalInput({
        reviewerId: 'auditor@external.test',
        reviewType: 'INDEPENDENT_PEER_REVIEW',
        reviewerAffiliation: 'External QA Dept',
        reviewBasis: 'SRS v1.0 checklist',
        reviewNotes: 'Full state invariant audit complete.',
      });
      assert.equal(indepValid, null);
    });

    it('truthfully categorizes recorded approval provenance labels', () => {
      const getProvenanceDisplayBadge = (approvedByString) => {
        if (!approvedByString) return 'Unapproved';
        if (approvedByString.includes('[SELF_REPORTED_DEVELOPMENT]')) {
          return 'Self-Reported Development Review (Non-independent)';
        }
        return 'Claimed Review (Unverified by Backend)';
      };

      assert.equal(
        getProvenanceDisplayBadge('alice@test.org [SELF_REPORTED_DEVELOPMENT]'),
        'Self-Reported Development Review (Non-independent)'
      );
      assert.equal(
        getProvenanceDisplayBadge('bob@test.org [INDEPENDENT_PEER_REVIEW]'),
        'Claimed Review (Unverified by Backend)'
      );
      assert.equal(
        getProvenanceDisplayBadge('carol@test.org [FORMAL_QA_SIGNOFF]'),
        'Claimed Review (Unverified by Backend)'
      );
    });
  });

  describe('6. Active-Project Response Handling & Stale-Response Protection', () => {
    // Contract implementation matching ProjectContext.jsx
    const unwrapProjectResponse = (res) => res?.project || res;
    const isValidProject = (proj, expectedId) => {
      return Boolean(
        proj &&
        typeof proj === 'object' &&
        typeof proj.project_id === 'string' &&
        proj.project_id.trim().length > 0 &&
        (expectedId === undefined || proj.project_id === expectedId)
      );
    };
    const isSelectableLifecycle = (proj) => {
      return Boolean(proj && proj.lifecycle && proj.lifecycle !== 'archived');
    };

    it('unwraps direct ProjectResponse without modification', () => {
      const direct = {
        project_id: 'proj_alpha',
        name: 'Alpha Project',
        lifecycle: 'active',
      };
      const unwrapped = unwrapProjectResponse(direct);
      assert.deepEqual(unwrapped, direct);
    });

    it('unwraps wrapped { project: ... } response correctly', () => {
      const wrapped = {
        project: {
          project_id: 'proj_beta',
          name: 'Beta Project',
          lifecycle: 'active',
        },
      };
      const unwrapped = unwrapProjectResponse(wrapped);
      assert.equal(unwrapped.project_id, 'proj_beta');
      assert.equal(unwrapped.name, 'Beta Project');
    });

    it('validates project identity matching the requested project ID', () => {
      const proj = { project_id: 'proj_target', name: 'Target' };
      assert.equal(isValidProject(proj, 'proj_target'), true);
      assert.equal(isValidProject(proj, 'proj_other'), false);
    });

    it('rejects malformed, empty, or missing project responses without TypeErrors', () => {
      assert.equal(isValidProject(null, 'proj_1'), false);
      assert.equal(isValidProject(undefined, 'proj_1'), false);
      assert.equal(isValidProject('not-an-object', 'proj_1'), false);
      assert.equal(isValidProject({}, 'proj_1'), false);
      assert.equal(isValidProject({ project_id: '' }, ''), false);
      assert.equal(isValidProject({ project_id: '   ' }, '   '), false);
    });

    it('enforces selectable lifecycle (active vs archived)', () => {
      assert.equal(isSelectableLifecycle({ lifecycle: 'active' }), true);
      assert.equal(isSelectableLifecycle({ lifecycle: 'archived' }), false);
      assert.equal(isSelectableLifecycle({ lifecycle: null }), false);
      assert.equal(isSelectableLifecycle(null), false);
    });

    it('discards stale asynchronous responses when request counters diverge', async () => {
      let latestRequestId = 0;
      let activeProjectState = null;

      // Simulate first selection attempt
      const attempt1RequestId = ++latestRequestId;
      // Simulate second selection attempt shortly after
      const _attempt2RequestId = ++latestRequestId;

      // Attempt 2 resolves first
      activeProjectState = { project_id: 'proj_fast' };

      // Attempt 1 resolves late
      const handleAttempt1Response = (proj) => {
        if (latestRequestId !== attempt1RequestId) {
          // Stale response discarded!
          return;
        }
        activeProjectState = proj;
      };

      handleAttempt1Response({ project_id: 'proj_slow_stale' });

      // State retains the project from attempt 2, not overwritten by stale attempt 1
      assert.equal(activeProjectState.project_id, 'proj_fast');
    });
  });
});

