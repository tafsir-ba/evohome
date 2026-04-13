import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { useSettings } from '../context/SettingsContext';

const SCRIPT_ID = 'google-translate-script';
const SOURCE_LANG = 'en';
const FULL_PAGE_TRANSLATE_PATHS = [
  /^\/agent\/feed(?:\/|$)/,
  /^\/agent\/documents(?:\/|$)/,
  /^\/agent\/workflow(?:\/|$)/,
  /^\/agent\/vault(?:\/|$)/,
  /^\/buyer(?:\/|$)/,
];

const setGoogleTranslateCookie = (targetLang) => {
  const value = `/${SOURCE_LANG}/${targetLang}`;
  document.cookie = `googtrans=${value};path=/`;

  const host = window.location.hostname;
  if (host.includes('.')) {
    document.cookie = `googtrans=${value};path=/;domain=.${host}`;
  }
};

export const GoogleTranslateAuto = () => {
  const { language } = useSettings();
  const location = useLocation();
  const initializedRef = useRef(false);
  const retryRef = useRef(null);
  const routeReapplyRef = useRef(null);
  const applyLanguageRef = useRef(() => {});

  const isFullPageTranslateRoute = () =>
    FULL_PAGE_TRANSLATE_PATHS.some((re) => re.test(location.pathname || ''));

  useEffect(() => {
    const stripGoogleBannerChrome = () => {
      try {
        document.body.style.top = '0px';
        document.documentElement.style.top = '0px';
        const banner = document.querySelector('.goog-te-banner-frame');
        if (banner) banner.remove();
        const skip = document.querySelector('iframe.goog-te-banner-frame');
        if (skip) skip.remove();
      } catch {
        // ignore cleanup errors
      }
    };

    const applyLanguage = (targetLang, { force = false } = {}) => {
      const normalized = targetLang === 'fr' ? 'fr' : 'en';
      setGoogleTranslateCookie(normalized);
      stripGoogleBannerChrome();

      if (retryRef.current) {
        window.clearInterval(retryRef.current);
        retryRef.current = null;
      }

      let attempts = 0;
      const tryApply = () => {
        const combo = document.querySelector('.goog-te-combo');
        if (combo) {
          if (!force && combo.value === normalized) {
            return true;
          }
          combo.value = normalized;
          combo.dispatchEvent(new Event('change'));
          return true;
        }
        return false;
      };

      if (tryApply()) return;

      retryRef.current = window.setInterval(() => {
        attempts += 1;
        const done = tryApply();
        if (done || attempts >= 12) {
          window.clearInterval(retryRef.current);
          retryRef.current = null;
        }
      }, 400);
    };
    applyLanguageRef.current = applyLanguage;

    const initGoogleTranslate = () => {
      if (initializedRef.current) return;
      if (!window.google || !window.google.translate) return;

      new window.google.translate.TranslateElement(
        {
          pageLanguage: SOURCE_LANG,
          includedLanguages: 'en,fr',
          autoDisplay: false,
        },
        'google_translate_element'
      );
      initializedRef.current = true;
      applyLanguage(language, { force: true });
    };

    window.googleTranslateElementInit = initGoogleTranslate;

    const existingScript = document.getElementById(SCRIPT_ID);
    if (!existingScript) {
      const script = document.createElement('script');
      script.id = SCRIPT_ID;
      script.src = 'https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
      script.async = true;
      document.body.appendChild(script);
    } else if (window.google && window.google.translate) {
      initGoogleTranslate();
    }

    return () => {
      if (retryRef.current) {
        window.clearInterval(retryRef.current);
        retryRef.current = null;
      }
      if (routeReapplyRef.current) {
        window.clearTimeout(routeReapplyRef.current);
        routeReapplyRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    const normalized = (language === 'fr' && isFullPageTranslateRoute()) ? 'fr' : 'en';
    applyLanguageRef.current(normalized, { force: true });
  }, [language, location.pathname]);

  useEffect(() => {
    // Re-apply translation once after route transitions.
    // Avoid MutationObserver loops that caused flicker/tremble.
    if (routeReapplyRef.current) {
      window.clearTimeout(routeReapplyRef.current);
    }
    routeReapplyRef.current = window.setTimeout(() => {
      const target = (language === 'fr' && isFullPageTranslateRoute()) ? 'fr' : 'en';
      applyLanguageRef.current(target, { force: false });
    }, 450);

    return () => {
      if (routeReapplyRef.current) {
        window.clearTimeout(routeReapplyRef.current);
        routeReapplyRef.current = null;
      }
    };
  }, [language, location.pathname, location.search]);

  return (
    <div
      id="google_translate_element"
      style={{
        position: 'fixed',
        left: '-9999px',
        top: 0,
        width: '1px',
        height: '1px',
        opacity: 0,
        pointerEvents: 'none',
      }}
      aria-hidden="true"
    />
  );
};

