import React from 'react';
import { Link, useNavigate } from 'react-router-dom';

/**
 * Clean Horizontal Breadcrumb Navigation Pill
 * Eliminates browser-default numbered list styling
 */
export default function Breadcrumbs({ items = [] }) {
  const navigate = useNavigate();

  if (!items || items.length === 0) return null;

  return (
    <nav className="clean-breadcrumb-nav font-mono" aria-label="Breadcrumb navigation">
      <button
        type="button"
        className="breadcrumb-back-btn"
        onClick={() => navigate('/')}
        title="Return to central map"
      >
        &larr; MAP
      </button>

      <span className="breadcrumb-divider-pipe">|</span>

      <div className="breadcrumb-pill-trail">
        {items.map((item, idx) => {
          const isLast = idx === items.length - 1;

          return (
            <React.Fragment key={item.label || idx}>
              <span className={`breadcrumb-segment ${isLast ? 'active' : ''}`}>
                {isLast || !item.to ? (
                  <span className="breadcrumb-current-label">
                    {item.label}
                  </span>
                ) : (
                  <Link to={item.to} className="breadcrumb-active-link">
                    {item.label}
                  </Link>
                )}
              </span>
              {!isLast && (
                <span className="breadcrumb-chevron-separator" aria-hidden="true">
                  &rsaquo;
                </span>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </nav>
  );
}
