import React from 'react';
import { Link } from 'react-router-dom';

/**
 * Standardized Municipal Breadcrumbs Component
 * Hierarchical navigation: Overview > Ranking > Hotspot (:gridId) [> Subview]
 */
export default function Breadcrumbs({ items = [] }) {
  if (!items || items.length === 0) return null;

  return (
    <nav className="municipal-breadcrumb-nav" aria-label="Breadcrumb">
      <ol className="breadcrumb-list">
        {items.map((item, idx) => {
          const isLast = idx === items.length - 1;

          return (
            <React.Fragment key={item.label || idx}>
              <li className={`breadcrumb-item ${isLast ? 'active' : ''}`}>
                {isLast || !item.to ? (
                  <span className="breadcrumb-current" aria-current="page">
                    {item.label}
                  </span>
                ) : (
                  <Link to={item.to} className="breadcrumb-link">
                    {item.label}
                  </Link>
                )}
              </li>
              {!isLast && (
                <li className="breadcrumb-separator" aria-hidden="true">
                  &rsaquo;
                </li>
              )}
            </React.Fragment>
          );
        })}
      </ol>
    </nav>
  );
}
