import { useState, useEffect } from "react";
import { BookmarkIcon } from "lucide-react";
import { Case } from "@/types/case";
import { ResultCard } from "@/components/search/result-card";
import { CaseDetailDialog } from "@/components/case-detail/case-detail-dialog";
import { useLocalStorage } from "@/lib/localStorageService";

export default function SavedCasesPage() {
  const [selectedCase, setSelectedCase] = useState<Case | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [savedCases, setSavedCases] = useState<Case[]>([]);
  
  const localStorage = useLocalStorage();

  // Fetch data from localStorage instead of API
  useEffect(() => {
    try {
      const cases = localStorage.getSavedCases();
      setSavedCases(cases);
      setIsLoading(false);
    } catch (error) {
      console.error("Error loading saved cases:", error);
      setIsLoading(false);
    }
  }, []);

  const handleViewCase = (caseData: Case) => {
    setSelectedCase(caseData);
    setDetailOpen(true);
  };

  // Updated to accept string ID to match Case interface
  const handleRemoveSavedCase = (id: string) => {
    localStorage.removeSavedCase(id);
    setSavedCases(localStorage.getSavedCases());
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 lg:p-6">
      <div className="mb-4">
        <h1 className="text-lg font-semibold text-secondary-900 dark:text-white">Saved Cases</h1>
        <p className="text-sm text-secondary-500 dark:text-secondary-400">
          {!isLoading && savedCases
            ? `${savedCases.length} case${savedCases.length !== 1 ? 's' : ''} saved`
            : 'Loading your saved cases...'}
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-white dark:bg-secondary-800 rounded-lg shadow-sm border border-secondary-200 dark:border-secondary-700 p-4 animate-pulse">
              <div className="h-5 w-2/3 bg-secondary-200 dark:bg-secondary-700 rounded mb-2"></div>
              <div className="h-4 w-1/3 bg-secondary-200 dark:bg-secondary-700 rounded mb-2"></div>
              <div className="h-4 w-full bg-secondary-200 dark:bg-secondary-700 rounded mb-1"></div>
              <div className="h-4 w-full bg-secondary-200 dark:bg-secondary-700 rounded mb-2"></div>
            </div>
          ))}
        </div>
      ) : savedCases?.length === 0 ? (
        <div className="bg-white dark:bg-secondary-800 rounded-lg shadow-sm border border-secondary-200 dark:border-secondary-700 p-6 text-center">
          <BookmarkIcon className="h-12 w-12 mx-auto text-secondary-400 mb-3" />
          <h3 className="text-lg font-medium text-secondary-900 dark:text-white mb-1">No Saved Cases</h3>
          <p className="text-secondary-600 dark:text-secondary-400 mb-4">
            You haven't saved any cases yet. When you find interesting cases, save them for quick access later.
          </p>
          <a href="/search" className="inline-flex items-center justify-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700">
            Start Searching
          </a>
        </div>
      ) : (
        <div className="space-y-4">
          {savedCases.map(caseItem => (
            <ResultCard
              key={caseItem.id}
              caseData={caseItem}
              onViewDetails={handleViewCase}
              onRemove={() => handleRemoveSavedCase(caseItem.id)}
              showRemoveButton
            />
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