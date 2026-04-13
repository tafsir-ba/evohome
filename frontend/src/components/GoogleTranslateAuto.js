import { useEffect, useRef } from 'react';
import { useSettings } from '../context/SettingsContext';

const SCRIPT_ID = 'google-translate-script';
const SOURCE_LANG = 'en';

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
  const initializedRef = useRef(false);
  const retryRef = useRef(null);

  useEffect(() => {
    const applyLanguage = (targetLang) => {
      const normalized = targetLang === 'fr' ? 'fr' : 'en';
      setGoogleTranslateCookie(normalized);

      if (retryRef.current) {
        window.clearInterval(retryRef.current);
        retryRef.current = null;
      }

      let attempts = 0;
      const tryApply = () => {
        const combo = document.querySelector('.goog-te-combo');
        if (combo) {
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
      applyLanguage(language);
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
    };
  }, []);

  useEffect(() => {
    const normalized = language === 'fr' ? 'fr' : 'en';
    setGoogleTranslateCookie(normalized);

    const combo = document.querySelector('.goog-te-combo');
    if (combo) {
      combo.value = normalized;
      combo.dispatchEvent(new Event('change'));
    }
  }, [language]);

  return <div id="google_translate_element" style={{ display: 'none' }} aria-hidden="true" />;
};

