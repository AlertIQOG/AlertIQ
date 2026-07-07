// types/correlation.ts

import type { CorrelationActionId } from "../correlation/actions";

// Represents a single condition within a correlation rule, as defined in the form
export interface CorrelationCondition {
  id: string;
  metric: string;
  operator: string;
  value: string;
}

// Represents the complete correlation rule model, as it will be stored in the database and displayed in the system
export interface CorrelationRule {
  id: string;
  name: string;
  isActive: boolean;

  // Time Window - a text field containing the number and unit (e.g., "45 Minutes")
  timeWindow: string;

  // Array of dynamic conditions from the form
  conditions?: CorrelationCondition[];

  // Actions to run when the rule matches (multiselect): "aggregate" and/or "email"
  actions?: CorrelationActionId[];

  // Recipients notified when the "email" action fires
  email_recipients?: string[];

  // Helper fields for table display
  logicSummary: {
    source: string;
    condition: string;
  };
  lastTriggered: string;
}