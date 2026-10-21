/**
 * Reference Workflow Input Template: E-Commerce Latest Paid Order Refund
 *
 * Sourced directly from the authoritative synthetic refund benchmark
 * (backend/app/components/c2_state_aware_workflow/examples/refund_workflow.py).
 */

export const getRefundWorkflowInputTemplate = (projectId = 'research_project_nexacart') => ({
  schema_version: '2026.1',
  project_id: projectId,
  domain: 'ecommerce',
  workflow_id: 'order_refund_workflow',
  name: 'Latest Paid Order Refund Workflow',
  version: '1.0.0',
  task: 'Refund my latest paid order.',
  business_rules: [
    {
      rule_id: 'RULE_OWNERSHIP',
      name: 'Customer Ownership',
      description: 'Orders must belong to the requesting customer (customer_id 42).',
      category: 'eligibility',
      priority: 1,
    },
    {
      rule_id: 'RULE_ELIGIBILITY_PAID',
      name: 'Paid Order Eligibility',
      description: "Only orders with payment_status == 'PAID' are eligible for refund.",
      category: 'eligibility',
      priority: 1,
    },
    {
      rule_id: 'RULE_LATEST_ORDER_SELECTION',
      name: 'Latest Order Selection and Tie-Breaking',
      description: 'Select the eligible order with the most recent created_at timestamp. Break ties using higher order_id.',
      category: 'ordering',
      priority: 2,
    },
    {
      rule_id: 'RULE_REJECT_UNPAID',
      name: 'Unpaid Order Rejection',
      description: 'An attempt to refund an unpaid or pending order must be cleanly rejected without modifying state.',
      category: 'rejection',
      priority: 1,
    },
    {
      rule_id: 'RULE_REFUND_EFFECT',
      name: 'Refund State Effect',
      description: "A successful refund creates a refund record and updates order payment_status to 'REFUNDED'.",
      category: 'effect',
      priority: 1,
    },
    {
      rule_id: 'RULE_PROTECTED_STATE_INVARIANT',
      name: 'Protected State Unaltered on Rejection',
      description: 'Rejection must leave order 502 status, order 501 status, and customer balance unaltered.',
      category: 'invariant',
      priority: 1,
    },
  ],
  tool_specifications: [
    {
      tool_name: 'get_customer_orders',
      description: 'Retrieve customer orders with payment status and placement timestamps.',
      parameters: [
        { name: 'customer_id', type: 'integer', description: 'Customer ID', required: true, default: null },
      ],
      return_type: 'list',
      has_side_effects: false,
    },
    {
      tool_name: 'get_order_details',
      description: 'Inspect detailed line items and pricing for a specific order.',
      parameters: [
        { name: 'order_id', type: 'integer', description: 'Order ID to inspect', required: true, default: null },
      ],
      return_type: 'dict',
      has_side_effects: false,
    },
    {
      tool_name: 'request_refund',
      description: 'Submit a refund request for an eligible order.',
      parameters: [
        { name: 'order_id', type: 'integer', description: 'Order ID to refund', required: true, default: null },
        { name: 'reason', type: 'string', description: 'Refund justification', required: false, default: 'customer_request' },
      ],
      return_type: 'dict',
      has_side_effects: true,
    },
    {
      tool_name: 'verify_refund_status',
      description: 'Verify that the refund transaction completed and database state updated.',
      parameters: [
        { name: 'order_id', type: 'integer', description: 'Order ID to verify', required: true, default: null },
      ],
      return_type: 'dict',
      has_side_effects: false,
    },
  ],
  observable_state_mappings: [
    {
      entity_type: 'orders',
      primary_key: 'id',
      observable_fields: ['id', 'customer_id', 'payment_status', 'amount', 'created_at'],
      description: 'Customer order records observed before and after refund events.',
    },
    {
      entity_type: 'refunds',
      primary_key: 'id',
      observable_fields: ['id', 'order_id', 'amount', 'status'],
      description: 'System refund ledger records.',
    },
  ],
  synthetic_fixture: {
    fixture_id: 'fixture_customer_42_refund',
    description: 'Fictional customer 42 with orders 501 (paid older), 502 (unpaid), and 503 (paid latest).',
    initial_entities: {
      customer: { id: 42, name: 'Alice Smith', balance: 0.0 },
      orders: {
        501: { id: 501, customer_id: 42, payment_status: 'PAID', amount: 55.0, created_at: '2026-10-10T10:00:00Z' },
        502: { id: 502, customer_id: 42, payment_status: 'UNPAID', amount: 120.0, created_at: '2026-10-12T12:00:00Z' },
        503: { id: 503, customer_id: 42, payment_status: 'PAID', amount: 85.5, created_at: '2026-10-15T15:00:00Z' },
      },
    },
    protected_state: {
      order_502_payment_status: 'UNPAID',
      customer_42_balance: 0.0,
    },
  },
  assumptions: [
    'Synthetic timestamps are ISO8601 strings.',
    'Abstract tool names represent simulated e-commerce operations without direct external API coupling.',
  ],
});
