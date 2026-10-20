import './setup';
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

describe('Component Shell Isolation and Name Verification', () => {
  const COMPONENT_NAMES = [
    'Explainable Tool-Call Correctness Testing',
    'State-Aware Multi-Step Workflow Testing',
    'Robustness and Failure Recovery Testing',
    'Policy-Aware Safety and Prompt-Injection Testing',
  ];

  it('preserves the exact required titles for all four components', () => {
    const appRoutesPath = path.resolve(__dirname, '../App.tsx');
    const appContent = fs.readFileSync(appRoutesPath, 'utf8');

    for (const name of COMPONENT_NAMES) {
      assert.equal(
        appContent.includes(name),
        true,
        `Expected App.tsx to include full title: "${name}"`
      );
    }
  });

  it('guarantees EmptyComponentPage contains no placeholder text or icons in its main body', () => {
    const emptyPagePath = path.resolve(
      __dirname,
      '../pages/shared/EmptyComponentPage.tsx'
    );
    const pageContent = fs.readFileSync(emptyPagePath, 'utf8');

    // Section 6 requirement: If a "No content yet" message currently appears inside the main component page, remove it
    assert.equal(pageContent.includes('No content yet'), false);
    assert.equal(pageContent.includes('PackageOpen'), false);
    assert.equal(pageContent.includes('empty-state-notice'), false);
  });

  it('guarantees no component API endpoints, SDKs, or services exist in frontend codebase', () => {
    const servicesDir = path.resolve(__dirname, '../services');
    const serviceFiles = fs.readdirSync(servicesDir);

    // Only api.ts, modelPreference.ts, and test/setup should exist
    for (const file of serviceFiles) {
      assert.equal(
        file.includes('c1_') ||
          file.includes('c2_') ||
          file.includes('c3_') ||
          file.includes('c4_') ||
          file.includes('tool_call') ||
          file.includes('workflow') ||
          file.includes('fault_injection') ||
          file.includes('safety'),
        false,
        `Unexpected component service found: ${file}`
      );
    }
  });

  it('verifies model preferences collect no API keys or secrets', () => {
    const modelPrefPath = path.resolve(
      __dirname,
      '../pages/shared/ModelSelectionPage.tsx'
    );
    const modelPrefContent = fs.readFileSync(modelPrefPath, 'utf8');

    // Must not ask for API keys, tokens, or credentials
    assert.equal(modelPrefContent.includes('apiKey'), false);
    assert.equal(modelPrefContent.includes('api_key'), false);
    assert.equal(modelPrefContent.includes('password'), false);
    assert.equal(modelPrefContent.includes('secret'), false);
  });
});
