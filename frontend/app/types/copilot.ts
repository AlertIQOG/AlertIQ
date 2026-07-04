export type CopilotConfidence = 'high' | 'medium' | 'low';

export interface CopilotStep {
  action: string;
  citations: number[];
}

export interface CopilotCitation {
  number: number;
  source_type: string;
  source_id: string;
  similarity: number;
  preview: string;
}

export interface CopilotSuggestion {
  alert_id: string;
  precedent_found: boolean;
  provider: string;
  cached: boolean;
  diagnosis: string | null;
  confidence: CopilotConfidence | null;
  steps: CopilotStep[];
  citations: CopilotCitation[];
}
