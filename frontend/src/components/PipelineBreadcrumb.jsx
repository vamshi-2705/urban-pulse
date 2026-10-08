import React from 'react';

export default function PipelineBreadcrumb({ pipeline }) {
  const defaultStages = [
    { step: 1, id: 'change', name: 'Change' },
    { step: 2, id: 'historical_baseline', name: 'Historical baseline' },
    { step: 3, id: 'local_baseline', name: 'Local baseline' },
    { step: 4, id: 'anomaly', name: 'Anomaly' },
    { step: 5, id: 'evidence', name: 'Evidence' },
    { step: 6, id: 'priority', name: 'Priority' },
    { step: 7, id: 'investigation_list', name: 'Investigation list' }
  ];

  const stages = pipeline?.stages || defaultStages;

  return (
    <section className="pipeline-bar" aria-label="Decision support pipeline stages">
      <div className="pipeline-header">
        <span className="pipeline-title">Evidence Pipeline Chain</span>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
          Transparent multi-stage derivation from satellite observations to field queue
        </span>
      </div>
      <div className="pipeline-chain">
        {stages.map((stage, idx) => (
          <React.Fragment key={stage.id}>
            <div
              className={`pipeline-step ${stage.id === 'investigation_list' ? 'step-active' : ''}`}
              title={stage.description || stage.name}
            >
              <span className="pipeline-step-num">{stage.step}</span>
              <span>{stage.name}</span>
            </div>
            {idx < stages.length - 1 && (
              <span className="pipeline-arrow" aria-hidden="true">→</span>
            )}
          </React.Fragment>
        ))}
      </div>
    </section>
  );
}
