import React from 'react';

/**
 * Compact Intelligence Workflow Strip
 * Communicates the core product paradigm:
 * OBSERVE → CHANGE → ANOMALY → EVIDENCE → PRIORITY
 */
export default function PipelineBreadcrumb({ activeStage = 'PRIORITY' }) {
  const stages = [
    { id: 'OBSERVE', label: 'OBSERVE', desc: 'Sentinel-2 L2A 10m Multi-spectral' },
    { id: 'CHANGE', label: 'CHANGE', desc: 'Normalized Temporal Deltas (NDVI/NDWI/NDBI)' },
    { id: 'ANOMALY', label: 'ANOMALY', desc: 'Scene-level & Local Spatial Deviation' },
    { id: 'EVIDENCE', label: 'EVIDENCE', desc: 'Multi-indicator Coherence & Persistence' },
    { id: 'PRIORITY', label: 'PRIORITY', desc: 'Explainable Triage & Field Verification' }
  ];

  return (
    <div className="workflow-strip" aria-label="Intelligence processing workflow">
      <div className="workflow-strip-label">WORKFLOW</div>
      <div className="workflow-steps-chain">
        {stages.map((stage, idx) => {
          const isActive = stage.id === activeStage;
          return (
            <React.Fragment key={stage.id}>
              <div
                className={`workflow-step ${isActive ? 'active' : ''}`}
                title={stage.desc}
              >
                <span className="workflow-step-num">0{idx + 1}</span>
                <span className="workflow-step-label">{stage.label}</span>
              </div>
              {idx < stages.length - 1 && (
                <span className="workflow-arrow" aria-hidden="true">→</span>
              )}
            </React.Fragment>
          );
        })}
      </div>
      <div className="workflow-meta">
        HYDERABAD AOI &bull; 1,462 CELLS (500m)
      </div>
    </div>
  );
}
