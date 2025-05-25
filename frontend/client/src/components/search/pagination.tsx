import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCallback } from "react";

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

export function Pagination({ currentPage, totalPages, onPageChange }: PaginationProps) {
  // Enhanced page change handler with reliable scroll to top
  const handlePageChange = useCallback((page: number) => {
    if (page === currentPage) return; // Don't do anything if clicking the current page
    
    // First trigger page change
    onPageChange(page);
    
    // Implement comprehensive scroll to top using all three recommended approaches
    // 1. Immediate scroll attempt
    window.scrollTo({ top: 0, behavior: 'auto' });
    
    // 2. Use requestAnimationFrame to ensure the DOM has updated
    requestAnimationFrame(() => {
      window.scrollTo({ top: 0, behavior: 'auto' });
      
      // Scroll document elements as well for maximum compatibility
      document.body.scrollTop = 0; // For Safari
      document.documentElement.scrollTop = 0; // For Chrome, Firefox, IE and Opera
      
      // Try to find and scroll the main content container if it exists
      const mainContent = document.querySelector('.search-results-container') || 
                          document.querySelector('main') || 
                          document.getElementById('main-content');
      if (mainContent) {
        (mainContent as HTMLElement).scrollTop = 0;
      }
    });
    
    // 3. Use a small timeout as a fallback
    setTimeout(() => {
      window.scrollTo({ top: 0, behavior: 'auto' });
      
      // Double-check scroll position and correct if needed
      if (window.scrollY > 0 || document.documentElement.scrollTop > 0) {
        window.scrollTo(0, 0);
        document.body.scrollTop = 0;
        document.documentElement.scrollTop = 0;
      }
    }, 10);
  }, [onPageChange, currentPage]);

  // Calculate page numbers to show
  const getPageNumbers = () => {
    const pageNumbers = [];

    // Always show first page
    pageNumbers.push(1);

    // Add ellipsis if not showing page 2
    if (currentPage > 3) {
      pageNumbers.push('ellipsis-1');
    }

    // Add page before current if not first page
    if (currentPage > 2) {
      pageNumbers.push(currentPage - 1);
    }

    // Add current page if not first or last
    if (currentPage !== 1 && currentPage !== totalPages) {
      pageNumbers.push(currentPage);
    }

    // Add page after current if not last page
    if (currentPage < totalPages - 1) {
      pageNumbers.push(currentPage + 1);
    }

    // Add ellipsis if not showing second-to-last page
    if (currentPage < totalPages - 2) {
      pageNumbers.push('ellipsis-2');
    }

    // Always show last page if more than 1 page
    if (totalPages > 1) {
      pageNumbers.push(totalPages);
    }

    return pageNumbers;
  };

  // Don't render pagination if only one page
  if (totalPages <= 1) {
    return null;
  }

  return (
    <div className="mt-6 flex justify-center">
      <div className="flex items-center space-x-1">
        <Button
          variant="outline"
          size="icon"
          onClick={() => handlePageChange(Math.max(1, currentPage - 1))}
          disabled={currentPage === 1}
          aria-label="Previous page"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        
        {getPageNumbers().map((page, index) => {
          if (page === 'ellipsis-1' || page === 'ellipsis-2') {
            return (
              <span key={`${page}`} className="px-2 text-secondary-500 dark:text-secondary-400">
                ...
              </span>
            );
          }
          
          return (
            <Button
              key={index}
              variant={currentPage === page ? "default" : "outline"}
              className={currentPage === page ? "bg-primary-600 text-white" : ""}
              onClick={() => handlePageChange(page as number)}
            >
              {page}
            </Button>
          );
        })}
        
        <Button
          variant="outline"
          size="icon"
          onClick={() => handlePageChange(Math.min(totalPages, currentPage + 1))}
          disabled={currentPage === totalPages}
          aria-label="Next page"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}