// types/correlation.ts

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
  
  // Helper fields for table display
  logicSummary: {
    source: string;
    condition: string;
  };
  lastTriggered: string;
}