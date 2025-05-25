import { createContext, useState, useContext, ReactNode, useCallback } from "react";
import { SortOption } from "@/types/case";

// Updated SearchFilters interface to match the data we actually have
export interface SearchFilters {
  courts: string[];
  dateFrom: string | null;
  dateTo: string | null;
  jurisdiction: string;
  caseType: string;
}

interface SearchContextType {
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  filters: SearchFilters;
  setFilters: (filters: SearchFilters) => void;
  sortBy: SortOption;
  setSortBy: (sort: SortOption) => void;
  recentSearches: string[];
  addRecentSearch: (search: string) => void;
}

const SearchContext = createContext<SearchContextType | undefined>(undefined);

export function SearchProvider({ children }: { children: ReactNode }) {
  const [searchQuery, setSearchQuery] = useState<string>("");
  
  // Updated default filter values
  const [filters, setFilters] = useState<SearchFilters>({
    courts: [],
    dateFrom: null,
    dateTo: null,
    jurisdiction: "all",
    caseType: "all"
  });
  
  const [sortBy, setSortBy] = useState<SortOption>(SortOption.Relevance);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);

  const addRecentSearch = useCallback((search: string) => {
    if (search.trim() === "") return;
    
    setRecentSearches(prev => {
      // Remove duplicate if it exists
      const filtered = prev.filter(s => s !== search);
      // Add to the beginning and limit to 10 items
      return [search, ...filtered].slice(0, 10);
    });
  }, []);

  return (
    <SearchContext.Provider value={{
      searchQuery,
      setSearchQuery,
      filters,
      setFilters,
      sortBy,
      setSortBy,
      recentSearches,
      addRecentSearch
    }}>
      {children}
    </SearchContext.Provider>
  );
}

export function useSearch() {
  const context = useContext(SearchContext);
  if (context === undefined) {
    throw new Error("useSearch must be used within a SearchProvider");
  }
  return context;
}