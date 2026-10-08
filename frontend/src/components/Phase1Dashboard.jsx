import React, { useState } from 'react';
import { fetchHotspotEvidence } from '../api/client';

export default function Phase1Dashboard({
  hotspots,
  healthInfo,
  overview,
  selectedHotspotId: controlledId,
  onSelectHotspot: setControlledId
}) {
  const [internalId, setInternalId] = useState(hotspots[0]?.id || hotspots[0]?.grid_id || null);
  const selectedHotspotId = controlledId || internalId;

  const [evidenceData, setEvidenceData] = useState(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceError, setEvidenceError] = useState(null);

  const handleSelectHotspot = async (hotspotId) => {
    if (setControlledId) {
      setControlledId(hotspotId);
    } else {
      setInternalId(hotspotId);
    }
    setEvidenceLoading(true);
    setEvidenceError(null);
    try {
      const data = await fetchHotspotEvidence(hotspotId);
      setEvidenceData(data);
    } catch (err) {
      setEvidenceError(err.message);
    } finally {
      setEvidenceLoading(false);
    }
  };

  // Automatically load evidence when selectedHotspotId changes
  React.useEffect(() => {
    if (selectedHotspotId) {
      handleSelectHotspot(selectedHotspotId);
    }
  }, [selectedHotspotId]);

  const getPriorityBadgeClass = (level) => {
    switch (level) {
      case 'high': return 'badge-high';
      case 'medium': return 'badge-medium';
      case 'normal':
      default: return 'badge-normal';
    }
  };

  const getCategoryBadgeClass = (category) => {
    switch (category) {
      case 'built_up_expansion': return 'badge-built-up';
      case 'vegetation_loss': return 'badge-vegetation';
      case 'water_body_change': return 'badge-water';
      case 'bare_land_change': return 'badge-bare';
      default: return 'badge-normal';
    }
  };

  const selectedHotspot = hotspots.find(h => h.id === selectedHotspotId || h.grid_id === selectedHotspotId || h.cellId === selectedHotspotId);

  return (
    <div className="main-layout">
      {/* Legal & Policy statement */}
      <div className="legal-notice-box" id="legal-notice">
        <strong>Municipal Decision-Support Notice:</strong>{' '}
        UrbanPulse flags unusual spatial divergence for prioritized field dispatch. It provides evidence-backed inspection queues rather than automated legal determinations. Field verification is recommended for all flagged locations.
      </div>

      <div className="content-grid">
        {/* Left Column: Prioritized Investigation List */}
        <section className="panel" aria-labelledby="queue-heading">
          <div className="panel-header">
            <div>
              <h2 className="panel-title" id="queue-heading">Prioritized Investigation List</h2>
              <p style={{ fontSize: '12px', marginTop: '2px' }}>
                Ranked sites requiring human attention first, based on anomalous multi-temporal land-cover transitions.
              </p>
            </div>
            <span className="badge badge-normal">
              {hotspots.length} sites ranked
            </span>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table className="data-table" aria-label="Investigation queue table">
              <thead>
                <tr>
                  <th style={{ width: '48px' }}>Rank</th>
                  <th>Cell / Ward</th>
                  <th>Category</th>
                  <th style={{ textAlign: 'right' }}>Priority score</th>
                  <th>Priority level</th>
                  <th>Observed change</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {hotspots.map((item) => {
                  const isSelected = item.id === selectedHotspotId;
                  return (
                    <tr
                      key={item.id}
                      style={{
                        backgroundColor: isSelected ? 'var(--bg-surface-selected)' : undefined,
                        cursor: 'pointer'
                      }}
                      onClick={() => handleSelectHotspot(item.id)}
                    >
                      <td style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
                        #{item.rank}
                      </td>
                      <td>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                          {item.wardName}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          ID: {item.cellId} ({item.zone})
                        </div>
                      </td>
                      <td>
                        <span className={`badge ${getCategoryBadgeClass(item.category)}`}>
                          {item.categoryLabel}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                        {item.priorityScore}
                      </td>
                      <td>
                        <span className={`badge ${getPriorityBadgeClass(item.priorityLevel)}`}>
                          {item.priorityLevel}
                        </span>
                      </td>
                      <td>
                        <div style={{ fontWeight: 500 }}>{item.keyMetric}</div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          {item.neighborhoodPercentile}
                        </div>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="btn"
                          style={{
                            fontSize: '11px',
                            padding: '3px 8px',
                            backgroundColor: isSelected ? 'var(--color-primary)' : undefined,
                            color: isSelected ? '#ffffff' : undefined
                          }}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSelectHotspot(item.id);
                          }}
                        >
                          {isSelected ? 'Inspecting' : 'Inspect evidence'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {/* Right Column: Evidence Inspector Chain */}
        <section className="panel" aria-labelledby="evidence-heading">
          <div className="panel-header">
            <div>
              <h2 className="panel-title" id="evidence-heading">Evidence Dossier</h2>
              <p style={{ fontSize: '12px', marginTop: '2px' }}>
                Verifiable pipeline records behind {selectedHotspot ? `#${selectedHotspot.rank} (${selectedHotspot.cellId})` : 'selected site'}
              </p>
            </div>
          </div>

          {evidenceLoading && (
            <p style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)' }}>
              Loading evidence records from mock provider...
            </p>
          )}

          {evidenceError && (
            <div style={{ padding: '12px', backgroundColor: 'var(--status-high-bg)', color: 'var(--status-high)', borderRadius: 'var(--radius-sm)' }}>
              Unable to load evidence dossier: {evidenceError}
            </div>
          )}

          {!evidenceLoading && !evidenceError && evidenceData && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Recommendation Callout */}
              <div
                style={{
                  padding: '12px',
                  backgroundColor: 'var(--status-high-bg)',
                  border: '1px solid var(--status-high-border)',
                  borderRadius: 'var(--radius-sm)'
                }}
              >
                <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--status-high)', fontWeight: 600 }}>
                  Directive
                </div>
                <div style={{ fontWeight: 600, color: 'var(--status-high)', marginTop: '2px' }}>
                  {evidenceData.recommendation || 'Unusual spatial change detected. Field verification recommended.'}
                </div>
              </div>

              {/* Chain Stage 1: Change */}
              <div style={{ padding: '12px', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-sm)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span style={{ fontWeight: 600, fontSize: '12px' }}>1. Observed Change</span>
                  <span className="badge badge-normal">Sentinel-2 MSI</span>
                </div>
                <p style={{ fontSize: '12px', marginBottom: '8px' }}>
                  {evidenceData.pipeline?.change?.observedChangeMetric}
                </p>
                {evidenceData.pipeline?.change?.metrics && (
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '4px' }}>
                    {evidenceData.pipeline.change.metrics.periods.map((period, i) => (
                      <div key={period} style={{ backgroundColor: '#ffffff', padding: '4px 6px', borderRadius: '3px' }}>
                        <div><strong>{period}</strong></div>
                        <div>Built-up: {evidenceData.pipeline.change.metrics.builtUpPercent[i]}%</div>
                        <div>Veg: {evidenceData.pipeline.change.metrics.vegetationPercent[i]}%</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Chain Stage 2 & 3: Baselines */}
              <div style={{ padding: '12px', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-sm)' }}>
                <div style={{ fontWeight: 600, fontSize: '12px', marginBottom: '6px' }}>2 & 3. Baseline Deviations</div>
                <div style={{ fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Historical baseline: </span>
                    <strong>{evidenceData.pipeline?.historicalBaseline?.deviationSummary}</strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Local neighborhood: </span>
                    <strong>{evidenceData.pipeline?.localBaseline?.percentileLabel}</strong>
                  </div>
                </div>
              </div>

              {/* Chain Stage 4: Anomaly */}
              <div style={{ padding: '12px', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-sm)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span style={{ fontWeight: 600, fontSize: '12px' }}>4. Anomaly & Persistence</span>
                  <span className={`badge ${getPriorityBadgeClass(evidenceData.pipeline?.anomaly?.compositeAnomalyLevel)}`}>
                    {evidenceData.pipeline?.anomaly?.compositeAnomalyLevel}
                  </span>
                </div>
                <p style={{ fontSize: '12px' }}>
                  {evidenceData.pipeline?.anomaly?.persistenceDetails}
                </p>
              </div>

              {/* Chain Stage 6: Priority Factor Breakdown */}
              {evidenceData.pipeline?.priority?.factorBreakdown && (
                <div style={{ padding: '12px', backgroundColor: 'var(--bg-surface-subtle)', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <span style={{ fontWeight: 600, fontSize: '12px' }}>6. Priority Factors (Score: {evidenceData.pipeline.priority.totalScore})</span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {evidenceData.pipeline.priority.factorBreakdown.map((f, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                        <span>{f.factor}</span>
                        <strong style={{ color: 'var(--color-primary)' }}>+{f.points}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {!evidenceLoading && !evidenceData && (
            <p style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
              Select a location from the queue to inspect its complete multi-stage evidence dossier.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
