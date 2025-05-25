import { useState, useRef, useEffect } from "react";
import { Search, History } from "lucide-react";
import { useSearch } from "@/context/search-context";
import { useKeyboardShortcut } from "@/hooks/use-keyboard-shortcut";

interface SearchSuggestion {
  type: "history" | "suggestion";
  text: string;
}

interface SearchBarProps {
  onSearch?: (query: string) => void;
}

export function SearchBar({ onSearch }: SearchBarProps) {
  const { searchQuery, setSearchQuery, recentSearches, addRecentSearch } = useSearch();
  const [localQuery, setLocalQuery] = useState(searchQuery);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestions, setSuggestions] = useState<SearchSuggestion[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  
  // Focus search input with keyboard shortcut (⌘+K / Ctrl+K)
  useKeyboardShortcut("k", () => {
    inputRef.current?.focus();
  }, { ctrl: true });
  
  useKeyboardShortcut("k", () => {
    inputRef.current?.focus();
  }, { meta: true });

  // Update suggestions when the input changes
useEffect(() => {
  if (localQuery.trim() === "") {
    setSuggestions(recentSearches.map(text => ({ type: "history", text })));
  } else {
    // Filter history items that match the query
    const historyItems: SearchSuggestion[] = recentSearches
      .filter(text => text.toLowerCase().includes(localQuery.toLowerCase()))
      .map(text => ({ type: "history", text }));
    
    const autoSuggestions: SearchSuggestion[] = [];
    if (localQuery.length >= 3) {
      // Add suggestions based on the query with variations
      if (!localQuery.toLowerCase().includes("case")) {
        autoSuggestions.push({ type: "suggestion", text: `${localQuery} cases` });
      }
      if (!localQuery.toLowerCase().includes("recent")) {
        autoSuggestions.push({ type: "suggestion", text: `recent ${localQuery}` });
      }
    }
    
    // Create a new array with explicit typing
    const combinedSuggestions: SearchSuggestion[] = [...historyItems, ...autoSuggestions];
    setSuggestions(combinedSuggestions.slice(0, 5));
  }
}, [localQuery, recentSearches]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (localQuery.trim()) {
      setSearchQuery(localQuery);
      addRecentSearch(localQuery);
      onSearch?.(localQuery);
      setShowSuggestions(false);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setLocalQuery(suggestion);
    setSearchQuery(suggestion);
    addRecentSearch(suggestion);
    onSearch?.(suggestion);
    setShowSuggestions(false);
  };

  return (
    <div className="w-full max-w-3xl relative">
      <form onSubmit={handleSubmit}>
        <div className="relative">
          <span className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-secondary-400">
            <Search className="h-4 w-4 text-secondary-400" />
          </span>
          <input 
            ref={inputRef}
            type="text" 
            className="block w-full pl-10 pr-16 py-2 border border-secondary-300 rounded-md bg-secondary-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 dark:bg-secondary-800 dark:border-secondary-700 dark:text-white" 
            placeholder="Search cases, statutes, or legal concepts..."
            value={localQuery}
            onChange={(e) => setLocalQuery(e.target.value)}
            onFocus={() => setShowSuggestions(true)}
            onBlur={() => {
              // Delay hiding suggestions to allow clicks on them
              setTimeout(() => setShowSuggestions(false), 200);
            }}
          />
          <div className="absolute inset-y-0 right-0 flex items-center pr-3 text-secondary-400">
            <kbd className="px-1.5 py-0.5 text-xs bg-secondary-200 dark:bg-secondary-700 rounded border border-secondary-300 dark:border-secondary-600 ml-1">⌘</kbd>
            <kbd className="px-1.5 py-0.5 text-xs bg-secondary-200 dark:bg-secondary-700 rounded border border-secondary-300 dark:border-secondary-600 ml-1">K</kbd>
          </div>
        </div>
      </form>
      
      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute mt-1 w-full rounded-md bg-white dark:bg-secondary-800 shadow-lg border border-secondary-200 dark:border-secondary-700 z-10">
          <ul>
            {suggestions.map((suggestion, index) => (
              <li 
                key={`${suggestion.text}-${index}`}
                className="px-4 py-2 hover:bg-secondary-100 dark:hover:bg-secondary-700 cursor-pointer flex items-center text-sm"
                onClick={() => handleSuggestionClick(suggestion.text)}
              >
                <span className="text-secondary-400 mr-2">
                  {suggestion.type === "history" ? <History className="h-4 w-4" /> : <Search className="h-4 w-4" />}
                </span>
                {suggestion.text}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
