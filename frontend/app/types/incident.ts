export type IncidentPriority = 'P1' | 'P2' | 'P3' | 'P4';
export type IncidentStage = 'Open' | 'In Progress' | 'Resolved';

export interface Incident {
  id: string;
  priority: IncidentPriority;
  title: string;
  assignee: string;
  stage: IncidentStage;
  createdAt: string;
  source: 'alert' | 'manual';
  linkedAlertId?: string;
  linkedAlertIds?: string[];
  linkedAlertTitle?: string;
  notes: string;
  affectedServices: string[];
}
