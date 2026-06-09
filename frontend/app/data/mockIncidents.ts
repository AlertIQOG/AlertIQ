import type { Incident } from '../types/incident';

export const mockIncidents: Incident[] = [
  {
    id: 'INC-1243',
    priority: 'P1',
    title: 'Database Outage Risk',
    assignee: 'Dana G.',
    stage: 'In Progress',
    createdAt: 'Today, 14:30',
    source: 'alert',
    linkedAlertTitle: 'Aggregated: DB Performance Degradation',
    notes: '',
    affectedServices: ['payments-api', 'auth-service', 'db-prod-cluster'],
  },
  {
    id: 'INC-1242',
    priority: 'P2',
    title: 'Consumer Lag Rising',
    assignee: 'John D.',
    stage: 'Open',
    createdAt: 'Today, 13:15',
    source: 'alert',
    linkedAlertTitle: 'Consumer Lag Rising',
    notes: '',
    affectedServices: ['orders-stream'],
  },
  {
    id: 'INC-1241',
    priority: 'P3',
    title: 'API Gateway Latency',
    assignee: 'Unassigned',
    stage: 'Resolved',
    createdAt: 'Yesterday, 09:00',
    source: 'manual',
    notes: 'Resolved after scaling the gateway.',
    affectedServices: ['api-gateway'],
  },
];
