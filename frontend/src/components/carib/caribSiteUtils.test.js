import { applyEvohomeCmpBranding } from '../gantt/ganttBrandingUtils';
import {
  CMP_DOCUMENT_TITLE,
  isCaribSite,
  isEvohomeCmpHost,
  isRemovedCaribHost,
} from './caribSiteUtils';

describe('carib site hosts', () => {
  test('app.carib-recon.org is removed and is not the CRC site', () => {
    expect(isRemovedCaribHost('app.carib-recon.org')).toBe(true);
    expect(isRemovedCaribHost('APP.CARIB-RECON.ORG')).toBe(true);
    expect(isCaribSite('app.carib-recon.org')).toBe(false);
  });

  test('app.evo-home.ch is the customer management platform, not CRC', () => {
    expect(isEvohomeCmpHost('app.evo-home.ch')).toBe(true);
    expect(isCaribSite('app.evo-home.ch', true)).toBe(false);
    expect(isCaribSite('app.carib-recon.org', true)).toBe(false);
    expect(isCaribSite('carib-recon.org', false)).toBe(true);
    expect(isCaribSite('www.carib-recon.org', false)).toBe(true);
    expect(isCaribSite('localhost', true)).toBe(true);
  });

  test('evohome host gets the customer management platform title and favicon', () => {
    document.head.innerHTML = '<meta name="description" content="Caribbean Regional Connectivity" />';
    document.title = 'Caribbean RE-Connect';

    applyEvohomeCmpBranding();

    expect(document.title).toBe(CMP_DOCUMENT_TITLE);
    expect(document.title).toBe('Customer Management Platform');
    const icon = document.querySelector("link[rel='icon'][data-cmp-branding='true']");
    expect(icon).not.toBeNull();
    expect(icon.getAttribute('href')).toBe('/evohome-logo.png');
    expect(document.querySelector('meta[name="description"]').getAttribute('content')).toBe(
      'Evohome - Real Estate Upgrade Management Platform',
    );
  });
});
