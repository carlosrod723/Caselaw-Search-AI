// Types for case data and search-related functionality

export interface Case {
  id: string;
  title: string;
  citation: string;
  court: string;
  date: string;
  summary: string;
  tags: string[];
  keyPassages?: string[];
  judges?: string;
  caseType?: string; // Added caseType field for case classification
}

// Define case type values as enum for type-safety
export enum CaseType {
  Criminal = "criminal",
  Civil = "civil",
  Administrative = "administrative",
  Constitutional = "constitutional",
  Disciplinary = "disciplinary"
}

export interface SearchResult {
  totalResults: number;
  page: number;
  totalPages: number;
  cases: Case[];
}

export enum SortOption {
  Relevance = "Relevance",
  DateNewest = "Date (newest)",
  DateOldest = "Date (oldest)"
}

// Updated SearchFilters interface to match our data capabilities
export interface SearchFilters {
  courts: string[];      
  court?: string;          
  dateFrom: string | null;
  dateTo: string | null;
  jurisdiction: string;
  caseType: string;
}