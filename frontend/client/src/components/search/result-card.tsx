import { useState, useEffect } from "react";
import { BookmarkIcon, Trash2, Gavel, FileText, Landmark, ScrollText, BadgeCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Case, CaseType } from "@/types/case";
import { formatLegalDate } from "@/lib/utils/citation-utils";
import { useToast } from "@/hooks/use-toast";
import { useLocalStorage } from "@/lib/localStorageService";

// Create a simple cache service for case enhancements
// Ideally, this would be in a separate file that's imported
const enhancementCache = {
  _cache: new Map<string, {
    summary: string;
    keyPassages: string[];
    timestamp: number;
  }>(),
  
  // Cache TTL - 1 hour
  TTL: 60 * 60 * 1000,
  
  get(caseId: string) {
    const cached = this._cache.get(caseId);
    if (!cached) return null;
    
    // Check for expiration
    if (Date.now() - cached.timestamp > this.TTL) {
      this._cache.delete(caseId);
      return null;
    }
    
    return cached;
  },
  
  set(caseId: string, data: { summary: string; keyPassages: string[] }) {
    this._cache.set(caseId, {
      ...data,
      timestamp: Date.now()
    });
  }
};

interface ResultCardProps {
  caseData: Case;
  onViewDetails: (caseData: Case) => void;
  onRemove?: (id: string) => void;
  showRemoveButton?: boolean;
}

export function ResultCard({ 
  caseData, 
  onViewDetails, 
  onRemove,
  showRemoveButton = false 
}: ResultCardProps) {
  console.log("Result card data:", {
    id: caseData.id,
    title: caseData.title,
    caseType: caseData.caseType
  });
  const [saved, setSaved] = useState(false);
  const { toast } = useToast();
  const localStorage = useLocalStorage();
  const [isPrefetching, setIsPrefetching] = useState(false);

  // Check if the case is saved when component mounts
  useEffect(() => {
    const savedCases = localStorage.getSavedCases();
    const isSaved = savedCases.some(c => c.id === caseData.id);
    setSaved(isSaved);
  }, [caseData.id]);

  // Prefetch the enhanced case data on hover
  const prefetchCaseData = async () => {
    // Skip if already prefetching or if data is already in cache
    if (isPrefetching || enhancementCache.get(caseData.id)) {
      return;
    }
    
    try {
      setIsPrefetching(true);
      const response = await fetch(`/api/v1/case/${caseData.id}/full`);
      
      if (response.ok) {
        const data = await response.json();
        
        // Store enhanced data in cache
        enhancementCache.set(caseData.id, {
          summary: data.summary || caseData.summary,
          keyPassages: data.keyPassages || []
        });
        
        console.log(`Prefetched case data for ${caseData.id}`);
      }
    } catch (error) {
      console.error("Error prefetching case data:", error);
    } finally {
      setIsPrefetching(false);
    }
  };

  // Handle viewing details with enhanced data if available
  const handleViewDetails = () => {
    // Check if we have enhanced data in cache
    const enhancedData = enhancementCache.get(caseData.id);
    
    if (enhancedData) {
      // Merge the enhanced data with the case data
      const enhancedCaseData = {
        ...caseData,
        summary: enhancedData.summary,
        keyPassages: enhancedData.keyPassages
      };
      
      // Call the onViewDetails with enhanced data
      onViewDetails(enhancedCaseData);
    } else {
      // If no enhanced data, just pass the original
      onViewDetails(caseData);
    }
  };

  const handleSaveToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    
    if (saved) {
      localStorage.removeSavedCase(caseData.id);
      setSaved(false);
    } else {
      localStorage.saveCase(caseData);
      setSaved(true);
    }
    
    toast({
      title: saved ? "Case removed from saved cases" : "Case saved to your library",
      description: saved ? "The case has been removed from your saved items." : "You can access this case from your saved cases.",
      variant: "default",
    });
  };

  return (
    <div 
      className="bg-white dark:bg-secondary-800 rounded-lg shadow-sm border border-secondary-200 dark:border-secondary-700 overflow-hidden hover:border-primary-300 dark:hover:border-primary-700 transition-colors cursor-pointer"
      onClick={handleViewDetails}
      onMouseEnter={prefetchCaseData}
    >
      <div className="p-4">
        <div className="flex justify-between items-start mb-2">
          <h2 className="text-lg font-medium text-primary-700 dark:text-primary-400 hover:underline">
            {caseData.title}
          </h2>

          {showRemoveButton && onRemove && (
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={(e) => {
                e.stopPropagation();
                onRemove(caseData.id);
              }}
              className="text-red-400 hover:text-red-600 dark:hover:text-red-400"
            >
              <Trash2 className="h-5 w-5" />
            </Button>
          )}
        </div>
        
        <div className="mb-3">
          <span className="font-serif italic text-sm text-secondary-600 dark:text-secondary-400">
            {caseData.court} • {formatLegalDate(caseData.date)}
            {caseData.judges && (
              <> • Judge: {caseData.judges}</>
            )}
          </span>
        </div>
        
        <p className="text-sm text-secondary-700 dark:text-secondary-300 mb-3 line-clamp-3">
          {caseData.summary}
        </p>
        
        <div className="flex flex-wrap gap-2 mb-3">
          {caseData.tags && caseData.tags.map((tag, index) => (
            <Badge 
              key={index} 
              variant={index === 0 ? "default" : "outline"}
              className={cn(
                index === 0 
                  ? "bg-primary-50 text-primary-700 hover:bg-primary-100 dark:bg-primary-900/30 dark:text-primary-400 dark:hover:bg-primary-900/50" 
                  : "bg-secondary-100 text-secondary-700 dark:bg-secondary-700 dark:text-secondary-300"
              )}
            >
              {tag}
            </Badge>
          ))}
        </div>
        
        {/* Footer with case type icon and bookmark button */}
        <div className="flex justify-end items-center gap-2 pt-2 border-t border-secondary-100 dark:border-secondary-700">
          {/* Bookmark button */}
          {!showRemoveButton && (
            <>
              {/* Case type icon */}
              <div className="flex-shrink-0">
                {caseData.caseType === CaseType.Criminal && (
                  <span className="flex items-center" aria-label="Criminal Case">
                    <Gavel className="h-4 w-4 text-red-500" />
                  </span>
                )}
                {caseData.caseType === CaseType.Civil && (
                  <span className="flex items-center" aria-label="Civil Case">
                    <FileText className="h-4 w-4 text-blue-500" />
                  </span>
                )}
                {caseData.caseType === CaseType.Administrative && (
                  <span className="flex items-center" aria-label="Administrative Case">
                    <Landmark className="h-4 w-4 text-amber-500" />
                  </span>
                )}
                {caseData.caseType === CaseType.Constitutional && (
                  <span className="flex items-center" aria-label="Constitutional Case">
                    <ScrollText className="h-4 w-4 text-green-500" />
                  </span>
                )}
                {caseData.caseType === CaseType.Disciplinary && (
                  <span className="flex items-center" aria-label="Disciplinary Case">
                    <BadgeCheck className="h-4 w-4 text-purple-500" />
                  </span>
                )}
              </div>
              
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={handleSaveToggle}
                className="text-secondary-400 hover:text-secondary-600 dark:hover:text-secondary-300"
              >
                <BookmarkIcon className={cn("h-5 w-5", saved && "fill-current")} />
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}