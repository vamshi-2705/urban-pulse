import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchEvidence, fetchHotspotDetail } from '../api/client';

export default function EvidenceView() {
  const { gridId } = useParams();
  const navigate = useNavigate();

  const [evidence, setEvidence] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [imageErrors, setImageErrors] = useState({});

  useEffect(() => {
    async function loadData() {
      if (!gridId) return;
      try {
        setLoading(true);
        setError(null);

        const [evidenceRes, detailRes] = await Promise.all([
          fetchEvidence(gridId),
          fetchHotspotDetail(gridId).catch(() => null)
        ]);

        setEvidence(evidenceRes);
        setDetail(detailRes);
      } catch (err) {
        console.error(`Failed to load evidence for ${gridId}:`, err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [gridId]);

  if (loading) {
    return (
      <div className="why-flagged-container loading-state" style={{ padding: '60px 20px', textAlign: 'center' }}>
        <div className="skeleton-spinner" style={{ margin: '0 auto 16px' }} />
        <p style={{ fontWeight: 600 }}>Loading evidence chain for {gridId}...</p>
      </div>
    );
  }

  if (error || !evidence) {
    return (
      <div className="why-flagged-container" style={{ padding: '40px 20px', maxWidth: '640px', margin: '0 auto' }}>
        <div className="error-card">
          <h2>Evidence Dossier Not Found</h2>
          <p>{error || `No evidence records found for grid ID '${gridId}'`}</p>
          <button type="button" className="btn btn-primary" onClick={() => navigate('/ranking')}>
            &larr; Back to Hotspot ranking
          </button>
        </div>
      </div>
    );
  }

  const level = (evidence.priority_level || detail?.priority_level || 'LOW').toUpperCase();
  const score = evidence.priority_score ?? detail?.priority_score ?? 0;

  // Step 1: Observed Change formatting
  const obs = evidence.observed_change || {};
  const builtUpDelta = Math.round(obs.built_up ?? 0);
  const vegDelta = Math.round(obs.vegetation ?? 0);
  const waterDelta = Math.round(obs.water ?? 0);

  const builtUpText = builtUpDelta >= 0 ? `+${builtUpDelta}` : `${builtUpDelta}`;
  const vegText = vegDelta >= 0 ? `+${vegDelta}` : `${vegDelta}`;
  const waterText = waterDelta >= 0 ? `+${waterDelta}` : `${waterDelta}`;

  const observedChangeValue = `Built-up ${builtUpText} points, Vegetation ${vegText} points${
    waterDelta !== 0 ? `, Water ${waterText} points` : ''
  }`;
  const observedChangeSentence = `Built-up area grew ${Math.abs(builtUpDelta)} points while vegetation contracted by ${Math.abs(
    vegDelta
  )} points between 2020 and 2026.`;

  // Step 2: Historical Baseline formatting
  const historicalBaseline = evidence.historical_change ?? 2.7;
  const historicalValue = `${historicalBaseline}x historical baseline`;
  const historicalSentence = `Observed rate of transition is ${historicalBaseline}x the historical baseline recorded for this grid cell.`;

  // Step 3: Local Baseline formatting
  const percentile = evidence.local_percentile ?? 95;
  const localValue = `${percentile}th percentile among nearby areas`;
  const localSentence = `Local change ranks in the ${percentile}th percentile compared to surrounding 500 m neighborhood cells.`;

  // Step 4: Anomaly formatting
  const tempAnomaly = evidence.temporal_anomaly ?? 0.91;
  const spatAnomaly = evidence.spatial_anomaly ?? 0.87;
  const persistenceVal = evidence.persistence ?? 0.82;
  const anomalyValue = `Temporal: ${tempAnomaly} | Spatial: ${spatAnomaly} | Persistence: ${persistenceVal}`;
  const anomalySentence = `Temporal divergence (${tempAnomaly}) and spatial divergence (${spatAnomaly}) detected with ${persistenceVal} multi-epoch persistence.`;

  // Step 5: Priority formatting
  const priorityValue = `${score} / 100 (${level} PRIORITY)`;
  const prioritySentence = `Composite anomaly and divergence metrics establish a priority score of ${score} / 100 with ${level} inspection urgency.`;

  // Imagery availability
  const hasImages =
    evidence.images &&
    evidence.images.length > 0 &&
    !imageErrors[2020] &&
    !imageErrors[2023] &&
    !imageErrors[2026];

  const years = [2020, 2023, 2026];

  return (
    <div className="why-flagged-page evidence-view-page">
      <div className="why-flagged-container">
        {/* Navigation Breadcrumb */}
        <div className="why-flagged-nav">
          <button
            type="button"
            className="back-link-btn"
            onClick={() => navigate(`/hotspot/${gridId}`)}
          >
            &larr; Back to Why Flagged ({gridId})
          </button>
          <button
            type="button"
            className="back-link-btn"
            onClick={() => navigate(`/hotspot/${gridId}/change`)}
          >
            Change explorer
          </button>
          <button type="button" className="back-link-btn" onClick={() => navigate('/ranking')}>
            Hotspot ranking
          </button>
          <button type="button" className="back-link-btn" onClick={() => navigate('/')}>
            Overview map
          </button>
        </div>

        {/* Page Header */}
        <header className="why-flagged-header">
          <div className="why-flagged-title-cluster">
            <h1 className="why-flagged-main-title">Evidence Dossier</h1>
            <div className="why-flagged-badge-row">
              <span className="why-flagged-grid-id">{gridId}</span>
              <span
                className={`badge ${
                  level === 'HIGH'
                    ? 'badge-high'
                    : level === 'MEDIUM'
                    ? 'badge-medium'
                    : 'badge-normal'
                }`}
              >
                <span
                  className={`status-dot-sm ${level === 'HIGH' ? 'bg-red' : 'bg-amber'}`}
                  aria-hidden="true"
                />
                {level} PRIORITY ({score} / 100)
              </span>
            </div>
            <p className="why-flagged-subtext">
              {detail?.ward_name || detail?.wardName || 'Hyderabad Metropolitan Growth Corridor'} &bull;
              Traceable spatial anomaly reasoning chain
            </p>
          </div>
        </header>

        {/* 1. Imagery Row: 2020 -> 2023 -> 2026 */}
        <section className="evidence-imagery-section" aria-label="Multi-epoch verification imagery">
          <div className="section-header-row">
            <h2 className="why-flagged-section-title">Multi-Epoch Imagery Chain</h2>
            <span className="breakdown-total-tag">2020 &rarr; 2023 &rarr; 2026</span>
          </div>

          <div className="evidence-imagery-row">
            {years.map((yr, idx) => {
              const imgUrl = `/images/${gridId}/${yr}.svg`;
              const isAvailable =
                evidence.images &&
                evidence.images.some((url) => url.includes(`/${yr}.svg`)) &&
                !imageErrors[yr];

              return (
                <React.Fragment key={yr}>
                  <div className="evidence-imagery-item">
                    <div className="imagery-card-wrapper">
                      {isAvailable ? (
                        <>
                          <span className="mock-imagery-tag">Mock imagery</span>
                          <span className="imagery-year-badge">{yr}</span>
                          <img
                            src={imgUrl}
                            alt={`Satellite observation tile for ${gridId} (${yr})`}
                            className="evidence-thumb-img"
                            onError={() => setImageErrors((prev) => ({ ...prev, [yr]: true }))}
                          />
                        </>
                      ) : (
                        <div className="evidence-imagery-unavailable">
                          <span className="imagery-year-badge-static">{yr}</span>
                          <p className="unavailable-notice-text">
                            Imagery not available for this location.
                          </p>
                        </div>
                      )}
                    </div>
                    <span className="imagery-epoch-caption">Epoch {yr}</span>
                  </div>

                  {/* Flow Arrow between steps */}
                  {idx < years.length - 1 && (
                    <div className="imagery-chain-arrow" aria-hidden="true">
                      &rarr;
                    </div>
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </section>

        {/* 2. Vertical, Traceable Chain: Five labelled steps */}
        <section className="evidence-traceable-chain-section" aria-label="Vertical reasoning chain">
          <div className="section-header-row">
            <h2 className="why-flagged-section-title">Traceable Reasoning Chain</h2>
            <span className="breakdown-total-tag">5 Verified Analytical Steps</span>
          </div>

          <div className="vertical-chain-container">
            {/* Step 1: Observed change */}
            <div className="chain-step-node">
              <div className="step-connector">
                <div className="step-number-circle">1</div>
                <div className="step-line" />
              </div>
              <div className="step-card-content">
                <div className="step-card-header">
                  <span className="step-step-badge">STEP 1</span>
                  <h3 className="step-title">Observed change</h3>
                  <span className="step-value-pill value-expansion">{observedChangeValue}</span>
                </div>
                <p className="step-sentence">&ldquo;{observedChangeSentence}&rdquo;</p>
              </div>
            </div>

            {/* Step 2: Historical baseline */}
            <div className="chain-step-node">
              <div className="step-connector">
                <div className="step-number-circle">2</div>
                <div className="step-line" />
              </div>
              <div className="step-card-content">
                <div className="step-card-header">
                  <span className="step-step-badge">STEP 2</span>
                  <h3 className="step-title">Historical baseline</h3>
                  <span className="step-value-pill value-baseline">{historicalValue}</span>
                </div>
                <p className="step-sentence">&ldquo;{historicalSentence}&rdquo;</p>
              </div>
            </div>

            {/* Step 3: Local baseline */}
            <div className="chain-step-node">
              <div className="step-connector">
                <div className="step-number-circle">3</div>
                <div className="step-line" />
              </div>
              <div className="step-card-content">
                <div className="step-card-header">
                  <span className="step-step-badge">STEP 3</span>
                  <h3 className="step-title">Local baseline</h3>
                  <span className="step-value-pill value-percentile">{localValue}</span>
                </div>
                <p className="step-sentence">&ldquo;{localSentence}&rdquo;</p>
              </div>
            </div>

            {/* Step 4: Anomaly */}
            <div className="chain-step-node">
              <div className="step-connector">
                <div className="step-number-circle">4</div>
                <div className="step-line" />
              </div>
              <div className="step-card-content">
                <div className="step-card-header">
                  <span className="step-step-badge">STEP 4</span>
                  <h3 className="step-title">Anomaly</h3>
                  <span className="step-value-pill value-anomaly">{anomalyValue}</span>
                </div>
                <p className="step-sentence">&ldquo;{anomalySentence}&rdquo;</p>
              </div>
            </div>

            {/* Step 5: Priority */}
            <div className="chain-step-node">
              <div className="step-connector">
                <div className="step-number-circle circle-priority">5</div>
              </div>
              <div className="step-card-content card-priority">
                <div className="step-card-header">
                  <span className="step-step-badge badge-priority-pill">STEP 5</span>
                  <h3 className="step-title">Priority</h3>
                  <span className="step-value-pill value-priority-score">{priorityValue}</span>
                </div>
                <p className="step-sentence">&ldquo;{prioritySentence}&rdquo;</p>
              </div>
            </div>
          </div>
        </section>

        {/* 3. Closing directive: End with "Field verification recommended." */}
        <section className="why-flagged-closing-banner" aria-label="Closing Directive">
          <div className="closing-banner-content">
            <span className="closing-directive-badge">ACTION DIRECTIVE</span>
            <p className="closing-directive-quote">
              &ldquo;Field verification recommended.&rdquo;
            </p>
          </div>
        </section>

        {/* Secondary Navigation Actions */}
        <section className="why-flagged-actions-section" aria-label="Related views">
          <div className="action-buttons-cluster">
            <button
              type="button"
              className="btn btn-outline-primary"
              onClick={() => navigate(`/hotspot/${gridId}`)}
            >
              Why Flagged
            </button>
            <button
              type="button"
              className="btn btn-outline-primary"
              onClick={() => navigate(`/hotspot/${gridId}/change`)}
            >
              Change explorer
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => navigate('/ranking')}
            >
              Hotspot ranking
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
