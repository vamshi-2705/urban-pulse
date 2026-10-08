import React from 'react';

/**
 * DevelopmentDataBanner
 *
 * Strict Requirement (Rule 3):
 * "While mock data is active the UI shows the 'Development data' banner. No hardcoded values in components."
 */
export default function DevelopmentDataBanner({ isMock, dataSource, legalNotice }) {
  if (!isMock) return null;

  return (
    <div className="dev-banner" id="dev-data-banner">
      <div className="dev-banner-left">
        <span className="dev-banner-tag">Development data</span>
        <span>
          Intelligence data source in development. Serving preloaded observations from <code>{dataSource || 'data/mock'}</code>.
        </span>
      </div>
      <div>
        <span>{legalNotice || 'Unusual spatial change detected. Field verification recommended.'}</span>
      </div>
    </div>
  );
}
