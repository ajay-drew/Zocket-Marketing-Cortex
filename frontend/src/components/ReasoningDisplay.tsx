import React from 'react';

interface ReasoningStep {
  step?: number;
  action?: string;
  reasoning?: string;
  decision?: string;
  tool?: string;
  tools?: string[];
  type?: string;
  original?: string;
  refined?: string;
  strategy?: string;
  sources?: string[];
  quality_score?: number;
  results_count?: number;
  overall_quality?: number;
  result_count?: number;
  next_action?: string;
}

interface ReasoningDisplayProps {
  reasoningSteps: ReasoningStep[];
}

// Brain Icon SVG Component
const BrainIcon: React.FC<{ className?: string }> = ({ className = "w-4 h-4" }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
    <path d="M12 19a4 4 0 0 0 4-4v-2" />
    <path d="M8 19a4 4 0 0 1 4-4v-2" />
    <path d="M12 19v-2" />
  </svg>
);

export const ReasoningDisplay: React.FC<ReasoningDisplayProps> = ({ reasoningSteps }) => {
  if (!reasoningSteps || reasoningSteps.length === 0) {
    return null;
  }

  const formatStep = (step: ReasoningStep, index: number): string => {
    const parts: string[] = [];

    // Query Analysis
    if (step.type === 'query_analysis' && step.analysis) {
      const analysis = step.analysis as any;
      parts.push(`Analyzed query: "${step.query}"`);
      parts.push(`Query type: ${analysis.query_type || 'mixed'}`);
      if (analysis.reasoning) {
        parts.push(`Reasoning: ${analysis.reasoning}`);
      }
      if (analysis.needed_tools && analysis.needed_tools.length > 0) {
        parts.push(`Selected tools: ${analysis.needed_tools.join(', ')}`);
      }
    }

    // Tool Call Start
    if (step.type === 'tool_call_start') {
      parts.push(`Executing tool: ${step.tool?.replace(/_/g, ' ') || 'unknown'}`);
      if (step.query) {
        parts.push(`Search query: "${step.query}"`);
      }
    }

    // Tool Call Result
    if (step.type === 'tool_call_result') {
      parts.push(`Tool "${step.tool?.replace(/_/g, ' ') || 'unknown'}" completed`);
      if (step.results_count !== undefined) {
        parts.push(`Found ${step.results_count} results`);
      }
      if (step.quality_score !== undefined) {
        parts.push(`Quality score: ${(step.quality_score * 100).toFixed(0)}%`);
      }
      if (step.reasoning) {
        parts.push(step.reasoning);
      }
    }

    // Evaluation
    if (step.type === 'evaluation') {
      if (step.overall_quality !== undefined) {
        parts.push(`Overall quality: ${(step.overall_quality * 100).toFixed(0)}%`);
      }
      if (step.result_count !== undefined) {
        parts.push(`Total results: ${step.result_count}`);
      }
      if (step.reasoning) {
        parts.push(step.reasoning);
      }
      if (step.next_action) {
        parts.push(`Next action: ${step.next_action === 'refine_query' ? 'Refine query' : 'Synthesize results'}`);
      }
    }

    // Query Refinement
    if (step.type === 'query_refinement') {
      parts.push(`Refining query: "${step.original}" → "${step.refined}"`);
      if (step.strategy) {
        parts.push(`Strategy: ${step.strategy}`);
      }
      if (step.reasoning) {
        parts.push(step.reasoning);
      }
    }

    // Synthesis Start
    if (step.type === 'synthesis_start') {
      if (step.sources && step.sources.length > 0) {
        parts.push(`Synthesizing from ${step.sources.length} sources: ${step.sources.join(', ')}`);
      }
      if (step.reasoning) {
        parts.push(step.reasoning);
      }
    }

    // Generic reasoning
    if (step.reasoning && !parts.includes(step.reasoning)) {
      parts.push(step.reasoning);
    }

    // Generic action/decision
    if (step.action && !parts.some(p => p.includes(step.action!))) {
      parts.push(`${step.action}`);
    }
    if (step.decision && !parts.some(p => p.includes(step.decision!))) {
      parts.push(step.decision);
    }

    return parts.length > 0 ? parts.join('. ') : `Step ${index + 1}`;
  };

  return (
    <div className="mb-4 pb-4 border-b border-gray-200">
      <div className="flex items-start gap-2 mb-3">
        <div className="flex-shrink-0 mt-0.5">
          <BrainIcon className="w-5 h-5 text-gray-500" />
        </div>
        <div className="flex-1">
          <h4 className="text-sm font-semibold text-gray-500 mb-2">Agent Reasoning</h4>
          <div className="space-y-2">
            {reasoningSteps.map((step, index) => {
              const stepText = formatStep(step, index);
              if (!stepText) return null;

              return (
                <div
                  key={index}
                  className="text-xs text-gray-600 leading-relaxed pl-2 border-l-2 border-gray-200"
                >
                  <span className="font-medium text-gray-500 mr-1">{index + 1}.</span>
                  {stepText}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
