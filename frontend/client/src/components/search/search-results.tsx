import { useEffect, useState, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpDown, SlidersHorizontal } from "lucide-react";
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { ResultCard } from "./result-card";
import { MobileFilters, DesktopFilters, QueryBuilder } from "./filters";
import { Pagination } from "./pagination";
import { CaseDetailDialog } from "@/components/case-detail/case-detail-dialog";
import { useSearch } from "@/context/search-context";
import { Case, SearchResult, SortOption, CaseType } from "@/types/case";
import { Skeleton } from "@/components/ui/skeleton";
import { useLocalStorage } from "@/lib/localStorageService";
import { transformSearchResponse, BackendSearchResponse, executeSearch, DEFAULT_PAGE_SIZE } from "@/lib/apiAdapter";
import { caseEnhancementCache } from "@/lib/caseEnhancementCache";

export function SearchResults() {
  const { searchQuery, sortBy, setSortBy, filters } = useSearch();
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedCase, setSelectedCase] = useState<Case | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const resultsContainerRef = useRef<HTMLDivElement>(null);
  
  // Debug log for page changes
  useEffect(() => {
    console.log(`Page changed to ${currentPage}, offset: ${(currentPage - 1) * 10}`);
  }, [currentPage]);
  
  // Reset to page 1 when search query or filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, filters]);
  
  // Query search results
  const {
    data: backendSearchResults,
    isLoading,
    error,
    isFetching
  } = useQuery<BackendSearchResponse>({
    queryKey: [
      'search', 
      searchQuery, 
      sortBy, 
      filters,
      currentPage
    ],
    queryFn: () => {
      console.log(`Executing search for page ${currentPage}, offset: ${(currentPage - 1) * 10}`);
      return executeSearch(
        searchQuery,
        sortBy,
        filters,
        DEFAULT_PAGE_SIZE,
        (currentPage - 1) * DEFAULT_PAGE_SIZE // offset
      ).then(response => {
        console.log(`Page ${currentPage} results:`, {
          total: response.total,
          total_available: response.total_available,
          first_id: response.results[0]?.metadata.case_id,
          last_id: response.results[response.results.length-1]?.metadata.case_id,
          result_ids: response.results.map(r => r.metadata.case_id).slice(0, 3) // First few IDs
        });
        return response;
      });
    },
    enabled: searchQuery.length > 0,
    placeholderData: (prev) => prev,
    refetchOnWindowFocus: false, // Don't refetch when window gets focus
    staleTime: 30000 // Data stays fresh for 30 seconds, reducing unnecessary refetches
  });
  
  // Log transformation input and output for debugging
  console.log("Transform input:", {
    query: backendSearchResults?.query,
    total: backendSearchResults?.total,
    total_available: backendSearchResults?.total_available,
    results_count: backendSearchResults?.results?.length
  });
  
  // Transform the backend response to the frontend format
  const searchResults = typeof backendSearchResults !== 'undefined'
    ? transformSearchResponse(backendSearchResults, currentPage)
    : undefined;
    
  console.log("Transform output:", {
    totalResults: searchResults?.totalResults,
    page: searchResults?.page,
    totalPages: searchResults?.totalPages,
    cases_count: searchResults?.cases?.length
  });
  
  // NEW: Prefetch case details when search results arrive
  useEffect(() => {
    if (searchResults?.cases && searchResults.cases.length > 0) {
      console.log(`Prefetching ${searchResults.cases.length} cases for enhanced details...`);
      caseEnhancementCache.prefetchCases(searchResults.cases);
    }
  }, [searchResults?.cases]);
  
  // Create a ref to track initial render
  const isInitialRender = useRef(true);
  
  // Setup scroll handling for cases when pagination component is not handling it
  // This is intentionally simplified to reduce conflicts with the Pagination component
  useEffect(() => {
    // Skip initial render
    if (isInitialRender.current) {
      isInitialRender.current = false;
      return;
    }
    
    // Only handle scroll for non-user-initiated page changes
    // (e.g., when triggered by code rather than pagination component clicks)
    const scrollIfNeeded = () => {
      // Check if we need to scroll (if we're not at the top)
      if (window.scrollY > 0 || document.documentElement.scrollTop > 0) {
        console.log('Auto-scrolling to top after programmatic page change');
        
        // Only scroll the container to avoid conflicting with Pagination component
        if (resultsContainerRef.current) {
          resultsContainerRef.current.scrollTop = 0;
        }
      }
    };
    
    // Only run if not loading - this indicates page change from API data, not user click
    if (!isLoading && !isFetching) {
      // Use requestAnimationFrame to wait for render
      requestAnimationFrame(scrollIfNeeded);
    }
  }, [currentPage, isLoading, isFetching]);
  
  const handleSortChange = (value: string) => {
    setSortBy(value as SortOption);
  };
  
  // UPDATED: Check cache for enhanced case data
  const handleViewCase = (caseData: Case) => {
    // Check if we have enhanced data in cache
    const cachedData = caseEnhancementCache.get(caseData.id);
    
    if (cachedData) {
      // Use cached enhanced data
      console.log(`Using cached data for case ${caseData.id}`);
      const enhancedCase = {
        ...caseData,
        summary: cachedData.summary,
        keyPassages: cachedData.keyPassages
      };
      setSelectedCase(enhancedCase);
    } else {
      // Use original data
      setSelectedCase(caseData);
      
      // Prioritize prefetching this case
      console.log(`Prioritizing prefetch for case ${caseData.id}`);
      caseEnhancementCache.prefetchCases([caseData], { priority: true });
    }
    
    setDetailOpen(true);
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 lg:p-6 search-results-container" ref={resultsContainerRef}>
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between mb-4">
        <div>
          <h1 className="text-lg font-semibold text-secondary-900 dark:text-white">Search Results</h1>
          {searchResults && (
            <p className="text-sm text-secondary-500 dark:text-secondary-400">
              Found {searchResults.totalResults.toLocaleString()} results for "{searchQuery}"
              {isFetching && (
                <span className="ml-1 inline-flex items-center">
                  <span className="animate-bounce mx-0.5 delay-0">.</span>
                  <span className="animate-bounce mx-0.5 delay-150">.</span>
                  <span className="animate-bounce mx-0.5 delay-300">.</span>
                </span>
              )}
            </p>
          )}
          {isLoading && !searchResults && (
            <p className="text-sm text-secondary-500 dark:text-secondary-400">
              Searching for "{searchQuery}"...
            </p>
          )}
          {error && (
            <p className="text-sm text-red-500">
              Error: Could not retrieve search results. Please try again.
            </p>
          )}
        </div>
        
        <div className="flex items-center space-x-2 mt-2 md:mt-0">
          <QueryBuilder />
          <label htmlFor="sort-by" className="text-sm text-secondary-500 dark:text-secondary-400 ml-2">Sort by:</label>
          <Select value={sortBy} onValueChange={handleSortChange}>
            <SelectTrigger id="sort-by" className="text-sm w-[140px]" aria-label="Sort results by">
              <SelectValue placeholder="Sort by" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={SortOption.Relevance}>Relevance</SelectItem>
              <SelectItem value={SortOption.DateNewest}>Date (newest)</SelectItem>
              <SelectItem value={SortOption.DateOldest}>Date (oldest)</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      
      <MobileFilters />
      
      <div className="flex mt-4">
        {/* Desktop filters - hidden on mobile */}
        <DesktopFilters />
        
        {/* Case Results */}
        <div className="flex-1 relative">
          {/* Subtle loading overlay for page transitions */}
          {isFetching && !isLoading && (
            <div className="absolute inset-0 bg-white/50 dark:bg-secondary-900/50 backdrop-blur-[1px] z-10 flex items-center justify-center">
              <div className="px-4 py-2 rounded-full bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400 text-sm font-medium animate-pulse">
                Loading page {currentPage}...
              </div>
            </div>
          )}
          
          <div className="space-y-4">
            {isLoading && !searchResults && (
              <>
                {[1, 2, 3].map((index) => (
                  <div key={index} className="bg-white dark:bg-secondary-800 rounded-lg shadow-sm border border-secondary-200 dark:border-secondary-700 overflow-hidden">
                    <div className="p-4">
                      <Skeleton className="h-6 w-3/4 mb-3" />
                      <Skeleton className="h-4 w-1/2 mb-3" />
                      <Skeleton className="h-4 w-full mb-2" />
                      <Skeleton className="h-4 w-full mb-2" />
                      <Skeleton className="h-4 w-2/3 mb-3" />
                      <div className="flex flex-wrap gap-2 mb-3">
                        <Skeleton className="h-6 w-24" />
                        <Skeleton className="h-6 w-32" />
                      </div>
                      <Skeleton className="h-6 w-full mt-3" />
                    </div>
                  </div>
                ))}
              </>
            )}
            
            {!isLoading && searchResults && searchResults.cases.length === 0 && (
              <div className="bg-white dark:bg-secondary-800 rounded-lg shadow-sm border border-secondary-200 dark:border-secondary-700 p-6 text-center">
                <ArrowUpDown className="h-12 w-12 mx-auto text-secondary-400 mb-3" />
                <h3 className="text-lg font-medium text-secondary-900 dark:text-white mb-1">No Results Found</h3>
                <p className="text-secondary-600 dark:text-secondary-400">
                  Try adjusting your search or filters to find what you're looking for.
                </p>
              </div>
            )}
            
            {searchResults && searchResults.cases.length > 0 &&
              searchResults.cases.map((caseItem: Case) => (
                <ResultCard
                  key={`page-${currentPage}-case-${caseItem.id}`}
                  caseData={caseItem}
                  onViewDetails={handleViewCase}
                />
              ))
            }
          </div>
          
          {/* Page number indicator */}
          {searchResults && searchResults.totalPages > 1 && (
            <div className="mt-3 text-center text-xs text-secondary-500 dark:text-secondary-400">
              Page {currentPage} of {searchResults.totalPages}
            </div>
          )}
          
          {/* Pagination */}
          {searchResults && searchResults.totalPages > 1 && (
            <div className="mt-3">
              <Pagination 
                currentPage={currentPage}
                totalPages={searchResults.totalPages}
                onPageChange={setCurrentPage}
              />
            </div>
          )}
        </div>
      </div>
      
      {/* Case Detail Dialog */}
      {selectedCase && (
        <CaseDetailDialog 
          caseData={selectedCase}
          open={detailOpen}
          onOpenChange={setDetailOpen}
        />
      )}
    </div>
  );
}