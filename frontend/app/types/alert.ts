export type AlertSeverity = 'Info' | 'Warning' | 'Error' | 'Critical';
export type AlertStatus = 'Open' | 'In progress' | 'Solved' | 'Dismissed';

export interface AlertNote {
  content: string;
  created_at: string;
}

export interface Alert {
  id: string;
  source_id: string;
  external_id: string;
  message: string;
  application?: string;
  component?: string;
  impact?: string;
  region?: string;
  node_name?: string;
  operator?: string;
  assignee?: string;
  severity: AlertSeverity;
  status: AlertStatus;
  extra_fields: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
  isAggregated?: boolean;
  childCount?: number;
}