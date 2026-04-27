export type AlertSeverity = 'Info' | 'Warning' | 'Error' | 'Critical';
export type AlertStatus = 'Open' | 'In progress' | 'Solved' | 'Dismissed';

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
  severity: AlertSeverity;
  status: AlertStatus;
  extra_fields: Record<string, unknown>;
  created_at?: string; 
  updated_at?: string;
  
  // Indicates if this alert is an aggregated alert representing multiple underlying alerts
  isAggregated?: boolean;
}