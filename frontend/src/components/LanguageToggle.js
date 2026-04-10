import { useSettings } from '../context/SettingsContext';
import { cn } from '../lib/utils';

export const LanguageToggle = () => {
  const { language, changeLanguage } = useSettings();

  return (
    <div 
      className="flex items-center bg-muted/50 rounded-lg p-0.5 text-sm"
      data-testid="language-toggle"
    >
      <button
        onClick={() => changeLanguage('en')}
        className={cn(
          "px-2.5 py-1 rounded-md font-medium transition-all duration-200",
          language === 'en'
            ? "bg-background text-foreground shadow-sm"
            : "text-muted-foreground hover:text-foreground"
        )}
        data-testid="lang-toggle-en"
      >
        EN
      </button>
      <button
        onClick={() => changeLanguage('fr')}
        className={cn(
          "px-2.5 py-1 rounded-md font-medium transition-all duration-200",
          language === 'fr'
            ? "bg-background text-foreground shadow-sm"
            : "text-muted-foreground hover:text-foreground"
        )}
        data-testid="lang-toggle-fr"
      >
        FR
      </button>
    </div>
  );
};
