/**
 * Column Configuration Registry
 * 
 * Defines all available columns for the AlertsTable along with their
 * display metadata. Used by the ColumnPicker to let users choose
 * which fields to show and by AlertsTable to render the selected columns.
 */

export interface ColumnConfig {
  key: string;
  label: string;
  description: string;
  defaultVisible: boolean;
  locked?: boolean;        // If true, cannot be toggled off (e.g. "message")
  category: 'core' | 'metadata' | 'timestamps';
}

export const ALL_COLUMNS: ColumnConfig[] = [
  // ── Core Fields ──────────────────────────────────────────────
  {
    key: 'severity',
    label: 'Severity',
    description: 'Alert severity level (Critical, Error, Warning, Info)',
    defaultVisible: true,
    category: 'core',
  },
  {
    key: 'status',
    label: 'Status',
    description: 'Current triage status of the alert',
    defaultVisible: true,
    category: 'core',
  },
  {
    key: 'message',
    label: 'Message',
    description: 'Alert message and external ID',
    defaultVisible: true,
    locked: true,
    category: 'core',
  },
  {
    key: 'region',
    label: 'Region',
    description: 'Deployment region (e.g. PROD, STG)',
    defaultVisible: true,
    category: 'core',
  },

  // ── Metadata Fields ──────────────────────────────────────────
  {
    key: 'application',
    label: 'Application',
    description: 'Application name and component',
    defaultVisible: true,
    category: 'metadata',
  },
  {
    key: 'component',
    label: 'Component',
    description: 'System component that triggered the alert',
    defaultVisible: false,
    category: 'metadata',
  },
  {
    key: 'impact',
    label: 'Impact',
    description: 'Business or operational impact assessment',
    defaultVisible: false,
    category: 'metadata',
  },
  {
    key: 'node_name',
    label: 'Node Name',
    description: 'Infrastructure node or host name',
    defaultVisible: false,
    category: 'metadata',
  },
  {
    key: 'operator',
    label: 'Operator',
    description: 'Operator or team responsible',
    defaultVisible: false,
    category: 'metadata',
  },
  {
    key: 'assignee',
    label: 'Assignee',
    description: 'User the alert is assigned to',
    defaultVisible: true,
    category: 'metadata',
  },
  {
    key: 'external_id',
    label: 'External ID',
    description: 'SHA-256 fingerprint or provider ID',
    defaultVisible: false,
    category: 'metadata',
  },

  // ── Timestamp Fields ─────────────────────────────────────────
  {
    key: 'created_at',
    label: 'Time',
    description: 'When the alert was created',
    defaultVisible: true,
    category: 'timestamps',
  },
  {
    key: 'updated_at',
    label: 'Updated At',
    description: 'When the alert was last modified',
    defaultVisible: false,
    category: 'timestamps',
  },
];

/** Column keys that are visible by default */
export const DEFAULT_VISIBLE_KEYS: string[] = ALL_COLUMNS
  .filter((c) => c.defaultVisible)
  .map((c) => c.key);

/** Storage key for persisting user preferences */
export const STORAGE_KEY = 'alertiq-visible-columns';

/** Category labels for grouping in the picker UI */
export const CATEGORY_LABELS: Record<string, string> = {
  core: 'Core Fields',
  metadata: 'Metadata',
  timestamps: 'Timestamps',
};
