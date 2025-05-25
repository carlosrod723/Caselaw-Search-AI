import { useState, useEffect } from "react";
import { HistoryIcon, Clock, Trash2 } from "lucide-react";
import { Case } from "@/types/case";
import { formatDate } from "@/lib/utils/date-utils";
import { ResultCard } from "@/components/search/result-card";
import { CaseDetailDialog } from "@/components/case-detail/case-detail-dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useLocalStorage, ActivityItem } from "@/lib/localStorageService";
import { caseEnhancementCache } from "@/lib/caseEnhancementCache";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";

export default function RecentActivityPage() {
  const [selectedCase, setSelectedCase] = useState<Case | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("all");
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingCase, setIsLoadingCase] = useState(false);
  const [recentActivity, setRecentActivity] = useState<ActivityItem[]>([]);
  
  const localStorage = useLocalStorage();
  const { toast } = useToast();

  // Fetch data from localStorage instead of API
  useEffect(() => {
    try {
      const activities = localStorage.getRecentActivity();
      setRecentActivity(activities);
      setIsLoading(false);
    } catch (error) {
      console.error("Error loading recent activity:", error);
      setIsLoading(false);
    }
  }, []);

  const handleViewCase = async (caseId: string) => {
    console.log(`[RecentActivity] Attempting to view case details for ID: ${caseId}`);
    
    // Use the component-level loading state for case loading
    setIsLoadingCase(true);
    
    try {
      // 1. First check if we can find the case in saved cases
      const savedCases = localStorage.getSavedCases();
      let caseData: Case | undefined = savedCases.find(c => c.id === caseId);
      
      if (caseData) {
        console.log(`[RecentActivity] Found case in saved cases: ${caseData.title}`);
        
        // Immediately set the selected case so the user can see it
        setSelectedCase(caseData);
        setDetailOpen(true);
        
        // Show success toast
        toast({
          title: "Case loaded from saved cases",
          description: `Viewing ${caseData.title}`,
          variant: "default"
        });
        
        // We'll continue to check for enhancements in the background
      }
      
      // 2. If not in saved cases, check basic case cache
      if (!caseData) {
        console.log(`[RecentActivity] Case not found in saved cases, checking cache for ID: ${caseId}`);
        const cachedCase = caseEnhancementCache.getBasicCase(caseId);
        
        if (cachedCase) {
          console.log(`[RecentActivity] Found case in basic cache: ${cachedCase.title}`);
          caseData = cachedCase;
          
          // Set the selected case immediately so the user can see it
          setSelectedCase(caseData);
          setDetailOpen(true);
          
          // Show informational toast that we're using cached data
          toast({
            title: "Using cached case data",
            description: "Loading case from local cache",
            variant: "default"
          });
        }
      }
      
      // 3. If not found locally, fetch from API with fixed endpoint order
      if (!caseData) {
        console.log(`[RecentActivity] Case not found locally, fetching from API for ID: ${caseId}`);
        
        // Show toast that we're fetching from API
        toast({
          title: "Fetching case",
          description: "Retrieving case details from the database...",
          variant: "default"
        });
        
        try {
          // UPDATED: First try the direct endpoint (no /basic suffix)
          console.log(`[RecentActivity] Trying main case endpoint for ID: ${caseId}`);
          const directResponse = await fetch(`/api/v1/case/${caseId}`);
          
          // If direct endpoint fails, try the /full endpoint
          if (!directResponse.ok) {
            console.log(`[RecentActivity] Main endpoint failed (${directResponse.status}), trying /full endpoint`);
            
            // Try the enhanced /full endpoint
            const fullResponse = await fetch(`/api/v1/case/${caseId}/full`);
            
            // Handle specific HTTP status codes
            if (fullResponse.status === 404) {
              console.log(`[RecentActivity] Case ${caseId} not found in database (404)`);
              throw new Error(`Case not found in database. It may have been removed or relocated.`);
            } else if (fullResponse.status === 403 || fullResponse.status === 401) {
              console.log(`[RecentActivity] Access denied for case ${caseId} (${fullResponse.status})`);
              throw new Error(`Access to this case is restricted (${fullResponse.status}).`);
            } else if (fullResponse.status >= 500) {
              console.log(`[RecentActivity] Server error when fetching case ${caseId} (${fullResponse.status})`);
              throw new Error(`Server error (${fullResponse.status}). Please try again later.`);
            } else if (!fullResponse.ok) {
              // As a last resort, try the /basic endpoint
              console.log(`[RecentActivity] /full endpoint failed (${fullResponse.status}), trying /basic endpoint`);
              const basicResponse = await fetch(`/api/v1/case/${caseId}/basic`);
              
              if (!basicResponse.ok) {
                throw new Error(`Failed to fetch case: ${basicResponse.statusText} (${basicResponse.status})`);
              }
              
              // Parse the basic response
              const basicData = await basicResponse.json();
              
              // Check if response data contains the required fields
              if (!basicData.id && !basicData.case_id) {
                console.error(`[RecentActivity] Invalid case data returned:`, basicData);
                throw new Error(`Invalid case data returned from server.`);
              }
              
              // Transform the data to match the Case interface
              caseData = transformResponseToCase(basicData, caseId);
            } else {
              // /full endpoint succeeded, process the response
              const fullData = await fullResponse.json();
              
              // Check if response data contains the required fields
              if (!fullData.id && !fullData.case_id) {
                console.error(`[RecentActivity] Invalid case data returned:`, fullData);
                throw new Error(`Invalid case data returned from server.`);
              }
              
              // Transform the data to match the Case interface (with enhanced data)
              caseData = transformResponseToCase(fullData, caseId);
              
              // This is already the enhanced version, so store it in the enhancement cache too
              if (caseData && caseData.summary) {
                caseEnhancementCache.set(caseId, {
                  summary: caseData.summary,
                  keyPassages: caseData.keyPassages || []
                });
              }
            }
          } else {
            // Direct endpoint worked, process the response
            const directData = await directResponse.json();
            
            // Check if response data contains the required fields
            if (!directData.id && !directData.case_id) {
              console.error(`[RecentActivity] Invalid case data returned:`, directData);
              throw new Error(`Invalid case data returned from server.`);
            }
            
            // Transform the data to match the Case interface
            caseData = transformResponseToCase(directData, caseId);
          }
          
          // If we got case data from API, display it immediately
          if (caseData) {
            console.log(`[RecentActivity] Successfully fetched case data from API: ${caseData.title}`);
            
            // Store in basic case cache for future use
            caseEnhancementCache.storeBasicCase(caseData);
            
            // Display the case to the user
            setSelectedCase(caseData);
            setDetailOpen(true);
            
            // Add to recent activity
            localStorage.addActivity('view', `Viewed: ${caseData.title}`, caseId);
            
            // Show success toast
            toast({
              title: "Case loaded successfully",
              description: `Viewing ${caseData.title}`,
              variant: "default"
            });
          }
        } catch (error) {
          console.error(`[RecentActivity] Error fetching case ${caseId}:`, error);
          
          // Format a user-friendly error message based on the error
          let errorMessage: string;
          
          if (error instanceof Error) {
            errorMessage = error.message;
          } else {
            errorMessage = `Failed to retrieve case data: Unknown error`;
          }
          
          // For network errors, provide specific guidance
          if (errorMessage.includes("Failed to fetch") || errorMessage.includes("NetworkError")) {
            errorMessage = "Network error. Please check your internet connection and try again.";
          }
          
          // Show user-friendly toast with option to remove from history
          toast({
            title: "Case not available",
            description: errorMessage,
            variant: "destructive",
            action: (
              <Button 
                variant="secondary" 
                onClick={() => {
                  // Find the activity item for this case and remove it
                  const activityItem = recentActivity.find(item => item.caseId === caseId);
                  if (activityItem) {
                    handleRemoveActivity(activityItem.id);
                    toast({
                      title: "Removed from history",
                      description: "The unavailable case has been removed from your history",
                      variant: "default"
                    });
                  }
                }}
                size="sm"
              >
                Remove
              </Button>
            )
          });
          
          // If we don't have case data yet, exit early
          if (!caseData) {
            setIsLoadingCase(false);
            return;
          }
        }
      }
      
      // 4. For cases we found in saved cases or cache, try to enhance with latest data
      if (caseData && !detailOpen) {
        // If the dialog isn't open yet (which means we didn't find the case in API),
        // display the case we've found from cache or saved cases
        setSelectedCase(caseData);
        setDetailOpen(true);
        
        // Check enhancement cache for additional data
        const cachedEnhancement = caseEnhancementCache.get(caseId);
        
        if (cachedEnhancement) {
          // Use cached enhanced data
          console.log(`[RecentActivity] Enhancing with cached data for case ${caseId}`);
          const enhancedCase = {
            ...caseData,
            summary: cachedEnhancement.summary || caseData.summary,
            keyPassages: cachedEnhancement.keyPassages || caseData.keyPassages || []
          };
          setSelectedCase(enhancedCase);
        } else {
          // Try to fetch the enhanced version in the background
          console.log(`[RecentActivity] Fetching enhanced data for case ${caseId} in background`);
          
          // Don't await this - let it happen in the background
          fetch(`/api/v1/case/${caseId}/full`)
            .then(response => {
              if (!response.ok) return null;
              return response.json();
            })
            .then(enhancedData => {
              if (enhancedData && (enhancedData.summary || enhancedData.keyPassages)) {
                // Store the enhanced data in cache
                caseEnhancementCache.set(caseId, {
                  summary: enhancedData.summary || "",
                  keyPassages: enhancedData.keyPassages || []
                });
                
                // Update the displayed case with enhanced data
                setSelectedCase(prev => {
                  if (!prev) return prev;
                  return {
                    ...prev,
                    summary: enhancedData.summary || prev.summary,
                    keyPassages: enhancedData.keyPassages || prev.keyPassages || []
                  };
                });
                
                console.log(`[RecentActivity] Successfully enhanced case ${caseId} in background`);
              }
            })
            .catch(error => {
              console.error(`[RecentActivity] Error enhancing case ${caseId} in background:`, error);
            });
        }
      }
      
      // If we somehow reached this point without any case data, show an error
      if (!caseData) {
        console.error(`[RecentActivity] No case data could be found for ID: ${caseId}`);
        
        toast({
          title: "Case not found",
          description: "This case is no longer available. It may have been removed from the database.",
          variant: "destructive",
          action: (
            <Button 
              variant="secondary" 
              onClick={() => {
                // Find the activity item for this case and remove it
                const activityItem = recentActivity.find(item => item.caseId === caseId);
                if (activityItem) {
                  handleRemoveActivity(activityItem.id);
                  toast({
                    title: "Removed from history",
                    description: "The unavailable case has been removed from your history",
                    variant: "default"
                  });
                }
              }}
              size="sm"
            >
              Remove
            </Button>
          )
        });
      }
    } catch (error) {
      console.error(`[RecentActivity] Unexpected error in handleViewCase for ${caseId}:`, error);
      
      // Create a user-friendly error message
      let errorMessage = "An unexpected error occurred while loading the case.";
      if (error instanceof Error) {
        errorMessage = error.message;
      }
      
      // Show error toast notification to the user
      toast({
        title: "Error retrieving case",
        description: errorMessage,
        variant: "destructive"
      });
    } finally {
      // Always stop loading regardless of success or failure
      setIsLoadingCase(false);
    }
  };
  
  // Helper function to transform API response to Case interface
  const transformResponseToCase = (responseData: any, caseId: string): Case => {
    return {
      id: responseData.id || responseData.case_id || caseId,
      title: responseData.title || responseData.name_abbreviation || responseData.name || `Case #${caseId}`,
      court: responseData.court || "Unknown Court",
      date: responseData.date || responseData.decision_date || "Unknown Date",
      citation: responseData.citation || "",
      summary: responseData.summary || "No summary available.",
      tags: responseData.jurisdiction ? [responseData.jurisdiction] : [],
      keyPassages: responseData.keyPassages || [],
      judges: responseData.judges || "",
      caseType: responseData.case_type || ""
    };
  };

  const handleRemoveActivity = (id: string) => {
    // Add this new function to handle removing activity items
    localStorage.removeActivityItem(id);
    setRecentActivity(prev => prev.filter(item => item.id !== id));
  };

  const filteredActivity = recentActivity?.filter(item => {
    if (activeTab === "all") return true;
    return item.type === activeTab;
  });

  return (
    <div className="flex-1 overflow-y-auto p-4 lg:p-6">
      <div className="mb-4">
        <h1 className="text-lg font-semibold text-secondary-900 dark:text-white">Recent Activity</h1>
        <p className="text-sm text-secondary-500 dark:text-secondary-400">
          Your research history and recently viewed cases
        </p>
      </div>

      <Tabs defaultValue="all" value={activeTab} onValueChange={setActiveTab} className="mb-6">
        <TabsList>
          <TabsTrigger value="all">All Activity</TabsTrigger>
          <TabsTrigger value="view">Viewed Cases</TabsTrigger>
          <TabsTrigger value="export">Exports</TabsTrigger>
        </TabsList>
      </Tabs>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-white dark:bg-secondary-800 rounded-lg shadow-sm border border-secondary-200 dark:border-secondary-700 p-4 animate-pulse">
              <div className="h-5 w-2/3 bg-secondary-200 dark:bg-secondary-700 rounded mb-2"></div>
              <div className="h-4 w-1/3 bg-secondary-200 dark:bg-secondary-700 rounded mb-2"></div>
              <div className="h-4 w-full bg-secondary-200 dark:bg-secondary-700 rounded"></div>
            </div>
          ))}
        </div>
      ) : isLoadingCase ? (
        <div className="bg-white dark:bg-secondary-800 rounded-lg shadow-sm border border-secondary-200 dark:border-secondary-700 p-6 text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-primary-600 border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite] mb-3"></div>
          <h3 className="text-lg font-medium text-secondary-900 dark:text-white mb-1">Loading Case</h3>
          <p className="text-secondary-600 dark:text-secondary-400">
            Retrieving case details from the database...
          </p>
        </div>
      ) : filteredActivity?.length === 0 ? (
        <div className="bg-white dark:bg-secondary-800 rounded-lg shadow-sm border border-secondary-200 dark:border-secondary-700 p-6 text-center">
          <HistoryIcon className="h-12 w-12 mx-auto text-secondary-400 mb-3" />
          <h3 className="text-lg font-medium text-secondary-900 dark:text-white mb-1">No Recent Activity</h3>
          <p className="text-secondary-600 dark:text-secondary-400 mb-4">
            You don't have any recent activity. Start searching or browsing cases to track your research.
          </p>
          <a href="/search" className="inline-flex items-center justify-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700">
            Start Researching
          </a>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredActivity?.map(item => (
            <div key={item.id} className="bg-white dark:bg-secondary-800 rounded-lg shadow-sm border border-secondary-200 dark:border-secondary-700 p-4">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center">
                  {item.type === 'view' && <Clock className="h-4 w-4 text-primary-500 mr-2" />}
                  {item.type === 'search' && <HistoryIcon className="h-4 w-4 text-green-500 mr-2" />}
                  {item.type === 'export' && <HistoryIcon className="h-4 w-4 text-amber-500 mr-2" />}
                  <span className="text-sm font-medium text-secondary-700 dark:text-secondary-300">
                    {item.type === 'view' && 'Viewed Case'}
                    {item.type === 'search' && 'Search Query'}
                    {item.type === 'export' && 'Exported Document'}
                  </span>
                </div>
                <div className="flex items-center">
                  <span className="text-xs text-secondary-500 dark:text-secondary-400 mr-3">
                    {formatDate(item.timestamp, 'MMM d, yyyy • h:mm a')}
                  </span>
                  {/* Add trash icon button */}
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    onClick={() => handleRemoveActivity(item.id)}
                    className="text-red-400 hover:text-red-600 dark:text-red-400 dark:hover:text-red-500"
                    aria-label="Remove from history"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              
              <p className="text-sm text-secondary-900 dark:text-white mb-2">
                {item.content}
              </p>
              
              {item.caseId && (
                <div className="mt-3 pt-3 border-t border-secondary-100 dark:border-secondary-700">
                  <button 
                    onClick={() => handleViewCase(item.caseId!)}
                    className="text-sm text-primary-600 hover:text-primary-700 dark:text-primary-400 hover:underline focus:outline-none"
                  >
                    View case details
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

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