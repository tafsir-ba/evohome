import { useState, useEffect, useRef } from 'react';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { cn } from '../lib/utils';
import { 
  Building2, 
  User, 
  Mail, 
  Phone, 
  MapPin,
  Plus,
  Search,
  Check,
  Loader2,
  X
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export const SupplierAutocomplete = ({
  value,
  onChange,
  onContactSelect,
  placeholder = "Search suppliers or enter new...",
  disabled = false,
  className
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState(value || '');
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedContact, setSelectedContact] = useState(null);
  const containerRef = useRef(null);
  const inputRef = useRef(null);

  // Fetch suggestions when search changes
  useEffect(() => {
    const fetchSuggestions = async () => {
      if (search.length < 1) {
        setSuggestions([]);
        return;
      }
      
      setLoading(true);
      try {
        const res = await fetch(
          `${API}/team/directory?search=${encodeURIComponent(search)}&limit=10`,
          { credentials: 'include' }
        );
        if (res.ok) {
          const data = await res.json();
          setSuggestions(data);
        }
      } catch (error) {
        console.error('Failed to fetch suggestions:', error);
      } finally {
        setLoading(false);
      }
    };

    const debounce = setTimeout(fetchSuggestions, 200);
    return () => clearTimeout(debounce);
  }, [search]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Sync external value changes
  useEffect(() => {
    if (value !== search) {
      setSearch(value || '');
    }
  }, [value]);

  const handleInputChange = (e) => {
    const newValue = e.target.value;
    setSearch(newValue);
    setSelectedContact(null);
    onChange(newValue);
    setIsOpen(true);
  };

  const handleSelectContact = (contact) => {
    setSearch(contact.company_name || contact.contact_name);
    setSelectedContact(contact);
    onChange(contact.company_name || contact.contact_name);
    setIsOpen(false);
    
    // Notify parent about full contact selection
    if (onContactSelect) {
      onContactSelect({
        supplier_name: contact.company_name || contact.contact_name,
        contact_person: contact.contact_name,
        email: contact.email,
        phone: contact.phone,
        address: contact.address
      });
    }
  };

  const clearSelection = () => {
    setSearch('');
    setSelectedContact(null);
    onChange('');
    inputRef.current?.focus();
  };

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
        <Input
          ref={inputRef}
          value={search}
          onChange={handleInputChange}
          onFocus={() => setIsOpen(true)}
          placeholder={placeholder}
          disabled={disabled}
          className={cn(
            "pl-9 pr-8",
            selectedContact && "border-primary/50 bg-primary/5"
          )}
          data-testid="supplier-autocomplete-input"
        />
        {search && (
          <button
            type="button"
            onClick={clearSelection}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Selected contact indicator */}
      {selectedContact && (
        <div className="mt-2 p-3 bg-primary/5 border border-primary/20 rounded-lg">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center flex-shrink-0">
              <Building2 className="w-5 h-5 text-primary" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-medium text-sm">{selectedContact.company_name || selectedContact.contact_name}</p>
              {selectedContact.contact_name && selectedContact.company_name && (
                <p className="text-xs text-muted-foreground">{selectedContact.contact_name}</p>
              )}
              <div className="flex flex-wrap gap-2 mt-1">
                {selectedContact.email && (
                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                    <Mail className="w-3 h-3" />
                    {selectedContact.email}
                  </span>
                )}
                {selectedContact.phone && (
                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                    <Phone className="w-3 h-3" />
                    {selectedContact.phone}
                  </span>
                )}
              </div>
            </div>
            <Check className="w-5 h-5 text-primary flex-shrink-0" />
          </div>
        </div>
      )}

      {/* Dropdown */}
      {isOpen && (search.length > 0 || suggestions.length > 0) && (
        <div className="absolute z-50 w-full mt-1 bg-popover border border-border rounded-lg shadow-lg max-h-80 overflow-y-auto">
          {loading ? (
            <div className="p-4 flex items-center justify-center">
              <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            </div>
          ) : suggestions.length > 0 ? (
            <ul className="py-1">
              {suggestions.map((contact) => (
                <li key={contact.member_id}>
                  <button
                    type="button"
                    onClick={() => handleSelectContact(contact)}
                    className="w-full px-3 py-2 text-left hover:bg-muted transition-colors flex items-start gap-3"
                    data-testid={`supplier-option-${contact.member_id}`}
                  >
                    <div className="w-9 h-9 bg-muted rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Building2 className="w-4 h-4 text-muted-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm">{contact.company_name || contact.contact_name}</p>
                      {contact.contact_name && contact.company_name && (
                        <p className="text-xs text-muted-foreground">{contact.contact_name}</p>
                      )}
                      <p className="text-xs text-primary">{contact.role}</p>
                      <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-0.5">
                        {contact.email && (
                          <span className="text-xs text-muted-foreground truncate max-w-[150px]">
                            {contact.email}
                          </span>
                        )}
                        {contact.phone && (
                          <span className="text-xs text-muted-foreground">
                            {contact.phone}
                          </span>
                        )}
                      </div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          ) : search.length > 0 ? (
            <div className="p-4 text-center">
              <p className="text-sm text-muted-foreground mb-2">No contacts found</p>
              <p className="text-xs text-muted-foreground">
                Type to use "{search}" as a new supplier
              </p>
            </div>
          ) : null}
          
          {/* Add to directory option */}
          {search.length > 2 && !suggestions.some(s => 
            (s.company_name || '').toLowerCase() === search.toLowerCase()
          ) && (
            <div className="border-t border-border p-2">
              <button
                type="button"
                onClick={() => {
                  onChange(search);
                  setIsOpen(false);
                }}
                className="w-full px-3 py-2 text-left hover:bg-muted rounded-md transition-colors flex items-center gap-2 text-sm"
              >
                <Plus className="w-4 h-4 text-primary" />
                <span>Use "{search}" as supplier name</span>
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SupplierAutocomplete;
