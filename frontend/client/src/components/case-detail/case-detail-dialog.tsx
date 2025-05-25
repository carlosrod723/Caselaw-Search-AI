import { useState, useEffect } from "react";

import { 
  Bookmark, 
  BookmarkIcon, 
  Share2, 
  Copy, 
  FileText, 
  Download as DownloadIcon,
  Clipboard,
  Mail
} from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator
} from "@/components/ui/dropdown-menu";

import { Button } from "@/components/ui/button";
import { Case } from "@/types/case";
import { formatLegalDate, generateCitation } from "@/lib/utils/citation-utils";
import { useToast } from "@/hooks/use-toast";
import { Separator } from "@/components/ui/separator";
import { localStorageService } from "@/lib/localStorageService";
import { caseEnhancementCache } from "@/lib/caseEnhancementCache";

interface CaseDetailDialogProps {
  caseData: Case;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CaseDetailDialog({ caseData: initialCaseData, open, onOpenChange }: CaseDetailDialogProps) {
  const [caseData, setCaseData] = useState(initialCaseData);
  const { toast } = useToast();
  
  // Loading state management
  const [isLoading, setIsLoading] = useState(false);
  const [hasEnhancedData, setHasEnhancedData] = useState(false);
  
  // Debug log for initial data
  useEffect(() => {
    console.log("[CaseDetailDialog] Rendered with initial data:", { 
      title: initialCaseData.title, 
      summaryLength: initialCaseData.summary?.length || 0 
    });
  }, [initialCaseData]);
  
  // Update state when props change
  useEffect(() => {
    console.log("[CaseDetailDialog] Props changed, updating state");
    setCaseData(initialCaseData);
  }, [initialCaseData]);

  // Detect if we need to show the loading state and fetch enhanced data
  useEffect(() => {
    if (!open) return; // Only run when dialog is open
    
    // Check if the case already has structured format
    const hasStructuredFormat = 
      caseData.summary?.includes("**Key Legal Issue") && 
      caseData.summary?.includes("**Holding") && 
      caseData.summary?.includes("**Reasoning");
    
    console.log("[CaseDetailDialog] Format check:", { 
      hasStructuredFormat,
      containsKeyLegalIssue: caseData.summary?.includes("**Key Legal Issue") || false,
      containsHolding: caseData.summary?.includes("**Holding") || false,
      containsReasoning: caseData.summary?.includes("**Reasoning") || false
    });
    
    // Set loading state and fetch enhanced data if needed
    if (hasStructuredFormat) {
      setIsLoading(false);
      setHasEnhancedData(true);
      console.log("[CaseDetailDialog] Already enhanced, skipping load");
    } else {
      setIsLoading(true);
      setHasEnhancedData(false);
      console.log("[CaseDetailDialog] Needs enhancement, showing loading state");
      fetchEnhancedData(caseData.id as string);
    }
  }, [open, caseData.id, caseData.summary]);
  
  console.log("[CaseDetailDialog] Current state:", { isLoading, hasEnhancedData });

  // Function to fetch enhanced case data
  const fetchEnhancedData = async (caseId: string) => {
    try {
      console.log("[CaseDetailDialog] Fetching enhanced data for:", caseId);
      const response = await fetch(`/api/v1/case/${caseId}/full`);
      
      if (!response.ok) {
        throw new Error(`Error fetching case details: ${response.statusText}`);
      }
      
      const enhancedData = await response.json();
      console.log("[CaseDetailDialog] Received enhanced data:", { 
        hasSummary: !!enhancedData.summary,
        hasKeyPassages: !!enhancedData.keyPassages,
        summaryLength: enhancedData.summary?.length || 0
      });
      
      // Update with enhanced data
      setCaseData(prevData => ({
        ...prevData,
        summary: enhancedData.summary || prevData.summary,
        keyPassages: enhancedData.keyPassages || [],
        judges: enhancedData.judges || prevData.judges,
      }));
      
      // Mark as loaded and having enhanced data
      setIsLoading(false);
      setHasEnhancedData(true);
      
    } catch (error) {
      console.error("[CaseDetailDialog] Error fetching enhanced data:", error);
      // Mark as not loading anymore even if there was an error
      setIsLoading(false);
    }
  };

  // Loading state component
  const SyllabusLoadingState = () => (
    <div className="space-y-4 animate-pulse">
      <div className="h-4 bg-secondary-200 dark:bg-secondary-700 rounded w-2/3"></div>
      <div className="h-4 bg-secondary-200 dark:bg-secondary-700 rounded w-5/6"></div>
      <div className="h-4 bg-secondary-200 dark:bg-secondary-700 rounded w-3/4"></div>
      <div className="space-y-2">
        <div className="h-4 bg-secondary-200 dark:bg-secondary-700 rounded w-full"></div>
        <div className="h-4 bg-secondary-200 dark:bg-secondary-700 rounded w-full"></div>
        <div className="h-4 bg-secondary-200 dark:bg-secondary-700 rounded w-5/6"></div>
      </div>
    </div>
  );
  
  // Extract key passages from text, avoiding duplicating syllabus content
  const extractKeyPassagesFromText = (caseData: Case): string[] => {
    // Check if we already have valid key passages from the backend
    if (caseData.keyPassages && 
        Array.isArray(caseData.keyPassages) && 
        caseData.keyPassages.length > 0 && 
        caseData.keyPassages.some(p => p && p.length >= 70)) {
      // Use existing passages if they meet quality criteria
      return caseData.keyPassages;
    }
    
    // If we have a full case text, use that; otherwise fall back to summary
    let fullText = "";
    
    // Try to access full content if available
    // Note: 'content' might come from the API response but isn't in our Case type
    const fullCaseContent = (caseData as any).content;
    
    if (fullCaseContent) {
      fullText = fullCaseContent;
    } else {
      // Fall back to summary if no full content available
      fullText = caseData.summary || "";
    }
    
    if (!fullText || fullText.length < 200) {
      console.log("Insufficient text to extract key passages");
      return [];
    }
    
    // Check if the summary contains the structured syllabus format
    const hasSyllabusHeadings = /\*\*Key Legal Issue|\*\*Holding|\*\*Reasoning/i.test(fullText);
    
    // Extract sentences from the text, avoiding syllabus content
    const extractedPassages: string[] = [];
    
    // Split the text into sentences
    const sentences = fullText.split(/(?<=[.!?])\s+/);
    
    // Legal keywords to look for in important passages
    const legalKeywords = [
      "we hold", "court held", "court found", "court ruled", "court concluded",
      "majority", "justice", "writes", "writing for", "dissent", "opinion",
      "amendment", "constitution", "statute", "pursuant to", "accordingly"
    ];
    
    // Words that indicate direct quotations
    const quoteIndicators = ["ruled that", "held that", "stated that", "concluded that", "found that"];
    
    // First, look for sentences that explicitly indicate court holdings
    for (const sentence of sentences) {
      // Skip short sentences or sentences from syllabus sections
      if (sentence.length < 70 || /\*\*Key Legal Issue|\*\*Holding|\*\*Reasoning/i.test(sentence)) {
        continue;
      }
      
      // Prioritize sentences with explicit holding language
      const containsHoldingLanguage = legalKeywords.some(keyword => 
        sentence.toLowerCase().includes(keyword.toLowerCase())
      );
      
      // Check if it looks like a genuine quote from the court opinion
      const looksLikeQuote = quoteIndicators.some(indicator => 
        sentence.toLowerCase().includes(indicator.toLowerCase())
      );
      
      // If it contains legal terminology and looks like a genuine passage, add it
      if ((containsHoldingLanguage || looksLikeQuote) && 
          !extractedPassages.includes(sentence)) {
        extractedPassages.push(sentence);
        
        // Stop after finding 2 good passages
        if (extractedPassages.length >= 2) {
          break;
        }
      }
    }
    
    // If we couldn't find passages with holding language, look for sentences 
    // that appear to be from the case text rather than summary
    if (extractedPassages.length < 2) {
      // Skip the first few paragraphs which might contain summary info
      const laterSentences = sentences.slice(Math.min(10, Math.floor(sentences.length / 3)));
      
      for (const sentence of laterSentences) {
        // Skip short sentences or sentences that might be from syllabus sections
        if (sentence.length < 70 || /\*\*Key Legal Issue|\*\*Holding|\*\*Reasoning/i.test(sentence)) {
          continue;
        }
        
        // Check for quotation marks which might indicate the text is quoting the court
        const hasQuotationMarks = sentence.includes('"') || sentence.includes('"') || sentence.includes('"');
        
        // Check for first person pronouns which might indicate direct court language
        const hasFirstPerson = /\b(we|our|us)\b/i.test(sentence);
        
        // If it has either quotation marks or first person language, consider it
        if ((hasQuotationMarks || hasFirstPerson) && 
            !extractedPassages.includes(sentence)) {
          extractedPassages.push(sentence);
          
          // Stop after finding 2 good passages
          if (extractedPassages.length >= 2) {
            break;
          }
        }
      }
    }
    
    // If we still don't have good passages, take sentences from the middle of the text
    // that don't match syllabus patterns to avoid duplication
    if (extractedPassages.length < 1) {
      // Try to find substantial sentences from the middle of the text
      const middleIndex = Math.floor(sentences.length / 2);
      const candidateSentences = sentences.slice(
        Math.max(middleIndex - 10, 0),
        Math.min(middleIndex + 10, sentences.length)
      );
      
      for (const sentence of candidateSentences) {
        // Exclude sentences that match syllabus section headings
        const isSyllabusSectionHeading = /\*\*Key Legal Issue|\*\*Holding|\*\*Reasoning/i.test(sentence);
        // Exclude sentences that are likely part of syllabus content
        const likelySyllabusContent = sentence.includes("The court ruled") || 
                                     sentence.includes("The central legal question") ||
                                     sentence.includes("The court found that");
        
        if (sentence.length >= 70 && 
            !isSyllabusSectionHeading && 
            !likelySyllabusContent &&
            !extractedPassages.includes(sentence)) {
          extractedPassages.push(sentence);
          
          // Only need one good passage at this point
          break;
        }
      }
    }
    
    // Return what we found, or empty array if nothing good was found
    return extractedPassages;
  };
  
  // On initial render and when case data changes, extract key passages if none exist
  useEffect(() => {
    // Only extract passages after we have enhanced data and no loading is happening
    if (hasEnhancedData && !isLoading && (!caseData.keyPassages || caseData.keyPassages.length === 0)) {
      console.log("[CaseDetailDialog] Extracting key passages");
      const extractedPassages = extractKeyPassagesFromText(caseData);
      
      if (extractedPassages.length > 0) {
        console.log("[CaseDetailDialog] Found key passages:", extractedPassages);
        setCaseData(prevData => ({
          ...prevData,
          keyPassages: extractedPassages
        }));
      } else {
        console.log("[CaseDetailDialog] No key passages found");
      }
    }
  }, [caseData.summary, hasEnhancedData, isLoading]);
  
  // Use the ID as defined in the Case type
  const caseId = caseData.id as string;
  
  const savedCases = localStorageService.getSavedCases();
  const [saved, setSaved] = useState(
    savedCases.some(c => c.id === caseId)
  );

  // Render the syllabus with proper sections
  const renderSyllabus = () => {
    // If we have no summary at all
    if (!caseData.summary) {
      return <p className="text-sm text-secondary-700 dark:text-secondary-300">No summary available.</p>;
    }
  
    // Check if summary has the structured format with section markers
    const hasStructuredFormat = 
      caseData.summary.includes("**Key Legal Issue") && 
      caseData.summary.includes("**Holding") && 
      caseData.summary.includes("**Reasoning");
  
    if (hasStructuredFormat) {
      try {
        // Extract content using regex to handle both formats (with or without colons)
        const keyIssueRegex = /\*\*Key Legal Issue:?\*\*([\s\S]*?)(?=\*\*Holding:?\*\*)/;
        const holdingRegex = /\*\*Holding:?\*\*([\s\S]*?)(?=\*\*Reasoning:?\*\*)/;
        const reasoningRegex = /\*\*Reasoning:?\*\*([\s\S]*?)$/;
      
        // Extract content using regex
        const keyIssueMatch = caseData.summary.match(keyIssueRegex);
        const holdingMatch = caseData.summary.match(holdingRegex);
        const reasoningMatch = caseData.summary.match(reasoningRegex);
      
        // Get content or fallback to empty string
        const keyIssueContent = keyIssueMatch ? keyIssueMatch[1].trim() : "";
        const holdingContent = holdingMatch ? holdingMatch[1].trim() : "";
        const reasoningContent = reasoningMatch ? reasoningMatch[1].trim() : "";
      
        console.log("Found structured syllabus sections:", { 
          keyIssueContent, 
          holdingContent, 
          reasoningContent 
        });
      
        return (
          <div className="space-y-4">
            {/* Key Legal Issue section */}
            {keyIssueContent && (
            <div>
              <h4 className="text-base font-medium text-secondary-800 dark:text-secondary-200">
                Key Legal Issue
              </h4>
              <p className="text-sm text-secondary-700 dark:text-secondary-300">
                {highlightKeyTerms(keyIssueContent)}
              </p>
            </div>
          )}
          
          {/* Holding section */}
          {holdingContent && (
            <div>
              <h4 className="text-base font-medium text-secondary-800 dark:text-secondary-200">
                Holding
              </h4>
              <p className="text-sm text-secondary-700 dark:text-secondary-300">
                {highlightKeyTerms(holdingContent)}
              </p>
            </div>
          )}
          
          {/* Reasoning section */}
          {reasoningContent && (
            <div>
              <h4 className="text-base font-medium text-secondary-800 dark:text-secondary-200">
                Reasoning
              </h4>
              <p className="text-sm text-secondary-700 dark:text-secondary-300">
                {highlightKeyTerms(reasoningContent)}
              </p>
            </div>
          )}
        </div>
      );
    } catch (error) {
      console.error("Error parsing structured syllabus:", error);
      // Fall back to showing full summary on error
      return (
        <p className="text-sm text-secondary-700 dark:text-secondary-300">
          {highlightKeyTerms(caseData.summary)}
        </p>
      );
    }
  }
  
  // For unstructured summary, just show the entire summary
  console.log("Using unstructured syllabus format");
  return (
    <p className="text-sm text-secondary-700 dark:text-secondary-300">
      {highlightKeyTerms(caseData.summary)}
    </p>
  );
};

  const highlightKeyTerms = (text: string) => {
    // Legal terms and phrases to highlight
    const legalTerms = [
      "held that", "we conclude", "therefore", "court finds",
      "rule", "statute", "constitution", "amendment",
      "rights", "plaintiff", "defendant", "judgment", "opinion",
      "majority", "dissent", "concur", "precedent", "affirmed",
      "reversed", "remanded", "vacated", "jurisdiction"
    ];
    
    // Create a regex pattern for all key phrases (case insensitive)
    // Use word boundaries to ensure we match whole words/phrases
    const pattern = new RegExp(`\\b(${legalTerms.join('|')})\\b`, 'gi');
    
    // Split the text and preserve the separators
    const parts = text.split(pattern);
    
    return parts.map((part, i) => {
      // Check if this part matches a legal term (case-insensitive)
      const isLegalTerm = legalTerms.some(term => 
        part.toLowerCase() === term.toLowerCase()
      );
      
      return isLegalTerm ? 
        <span key={i} className="bg-yellow-100 dark:bg-yellow-900/30 font-medium">{part}</span> : 
        <span key={i}>{part}</span>;
    });
  };

  const handleSaveToggle = () => {
    const newSavedState = !saved;
    setSaved(newSavedState);
    
    if (newSavedState) {
      localStorageService.saveCase(caseData);
    } else {
      localStorageService.removeSavedCase(caseId);
    }
    
    toast({
      title: saved ? "Case removed from saved cases" : "Case saved to your library",
      description: saved ? "The case has been removed from your saved items." : "You can access this case from your saved cases.",
      variant: "default",
    });
  };

  // Share functionality - split into separate functions
  const handleCopyLink = () => {
    // Use the environment variable with fallback to window.location.origin
    const baseUrl = import.meta.env.VITE_APP_URL || window.location.origin;
    const shareableLink = `${baseUrl}/case/${caseId}`;
    
    navigator.clipboard.writeText(shareableLink);
    
    toast({
      title: "Link copied to clipboard",
      description: "You can now share this case with others.",
      variant: "default",
    });
    
    localStorageService.addActivity('export', `Copied link: ${caseData.title}`, caseId);
  };

  const handleEmailShare = () => {
    // Use the environment variable with fallback to window.location.origin
    const baseUrl = import.meta.env.VITE_APP_URL || window.location.origin;
    const shareableLink = `${baseUrl}/case/${caseId}`;
    
    // Improve formatting with line breaks
    const subject = encodeURIComponent(`Legal Case: ${caseData.title}`);
    const body = encodeURIComponent(
      `I thought you might be interested in this legal case:\n\n` +
      `${caseData.title}\n` +
      `${caseData.court} (${formatLegalDate(caseData.date)})\n` +
      `Citation: ${caseData.citation}\n\n` +
      `View the case here: ${shareableLink}`
    );
    
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
    
    toast({
      title: "Email client opened",
      description: "An email has been prepared with the case details.",
      variant: "default",
    });
    
    localStorageService.addActivity('export', `Shared via email: ${caseData.title}`, caseId);
  };

  const handleWebShare = () => {
    // Use the environment variable with fallback to window.location.origin
    const baseUrl = import.meta.env.VITE_APP_URL || window.location.origin;
    const shareableLink = `${baseUrl}/case/${caseId}`;
    
    if (typeof navigator.share === 'function') {
      navigator.share({
        title: caseData.title,
        text: `${caseData.title} - ${caseData.court} (${formatLegalDate(caseData.date)})`,
        url: shareableLink,
      })
      .then(() => {
        toast({
          title: "Shared successfully",
          description: "The case has been shared.",
          variant: "default",
        });
        
        localStorageService.addActivity('export', `Shared via Web Share API: ${caseData.title}`, caseId);
      })
      .catch((error) => {
        console.error('Error sharing:', error);
        // Fall back to clipboard if sharing fails
        handleCopyLink();
      });
    } else {
      toast({
        title: "Sharing not supported",
        description: "This feature is not supported on your browser. The link has been copied instead.",
        variant: "default",
      });
      handleCopyLink();
    }
  };
  
  const handleCopyCitation = (format: 'bluebook' | 'apa' | 'chicago' = 'bluebook') => {
    const citation = generateCitation(
      caseData.title,
      caseData.citation,
      caseData.court,
      caseData.date,
      format
    );
    
    navigator.clipboard.writeText(citation);
    
    toast({
      title: `${format.toUpperCase()} citation copied`,
      description: "The formatted citation has been copied to your clipboard.",
      variant: "default",
    });
    
    localStorageService.addActivity('export', `Copied ${format} citation: ${caseData.title}`, caseId);
  };

  // Function to fetch the full document
  const fetchFullDocument = async () => {
    // Add diagnostic log at the beginning
    console.log("fetchFullDocument called for case ID:", caseId);
    
    try {
      const response = await fetch(`/api/v1/case/${caseId}/full`);
      
      if (!response.ok) {
        throw new Error(`Error fetching document: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      // Add detailed diagnostic logs
      console.log("Full document response data:", data);
      
      // Transform the backend response to match frontend Case interface
      const transformedData = {
        ...data,
        id: data.case_id || caseId,
        citation: data.citation || "",
        tags: data.jurisdiction ? [data.jurisdiction] : [],
      };
      
      return transformedData;
    } catch (error) {
      console.error("Error fetching full document:", error);
      toast({
        title: "Error fetching document",
        description: "Unable to retrieve the full document. Please try again later.",
        variant: "destructive",
      });
      return null;
    }
  };

  // Handle document preview
  const handlePreviewDocument = async () => {
    // 1. Open window first, directly from click event
    const previewWindow = window.open("about:blank", "_blank");
    
    // 2. Check if popup was blocked
    if (!previewWindow) {
      toast({
        title: "Popup blocked",
        description: "Please allow popups to preview the document.",
        variant: "destructive",
      });
      return;
    }
    
    // 3. Show loading indicator while fetching
    previewWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Loading ${caseData.title}...</title>
        <style>
          :root {
            --primary-color: #2563eb;
            --primary-dark: #1d4ed8;
            --text-dark: #333;
            --text-light: #666;
            --background: #f9fafb;
            --border: #e5e7eb;
          }
          
          @media (prefers-color-scheme: dark) {
            :root {
              --primary-color: #3b82f6;
              --primary-dark: #60a5fa;
              --text-dark: #e5e7eb;
              --text-light: #9ca3af;
              --background: #111827;
              --border: #374151;
            }
            body {
              background-color: var(--background);
              color: var(--text-dark);
            }
          }
          
          body { 
            font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif; 
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
            background-color: var(--background);
            color: var(--text-dark);
          }
          
          .container {
            width: 100%;
            max-width: 700px;
            text-align: center;
          }
          
          .case-title {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
          }
          
          .case-info {
            font-size: 1rem;
            font-weight: 400;
            color: var(--text-light);
            font-style: italic;
            margin-bottom: 2rem;
          }
          
          .loading-text {
            margin-bottom: 1.5rem;
            font-size: 1.1rem;
          }
          
          .skeleton {
            background: linear-gradient(90deg, rgba(0,0,0,0.06) 25%, rgba(0,0,0,0.12) 50%, rgba(0,0,0,0.06) 75%);
            background-size: 200% 100%;
            animation: shimmer 1.5s infinite;
            border-radius: 4px;
            margin-bottom: 12px;
            height: 12px;
          }
          
          @media (prefers-color-scheme: dark) {
            .skeleton {
              background: linear-gradient(90deg, rgba(255,255,255,0.06) 25%, rgba(255,255,255,0.12) 50%, rgba(255,255,255,0.06) 75%);
              background-size: 200% 100%;
            }
          }
          
          .skeleton:nth-child(1) { width: 100%; }
          .skeleton:nth-child(2) { width: 92%; }
          .skeleton:nth-child(3) { width: 96%; }
          .skeleton:nth-child(4) { width: 90%; }
          .skeleton:nth-child(5) { width: 94%; }
          .skeleton:nth-child(6) { width: 88%; }
          
          .spinner {
            width: 50px;
            height: 50px;
            border: 3px solid rgba(0, 0, 0, 0.1);
            border-radius: 50%;
            border-top-color: var(--primary-color);
            animation: spin 1s ease-in-out infinite;
            margin: 0 auto 1.5rem;
          }
          
          @media (prefers-color-scheme: dark) {
            .spinner {
              border-color: rgba(255, 255, 255, 0.1);
              border-top-color: var(--primary-color);
            }
          }
          
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
          
          @keyframes shimmer {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
          }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="case-title">${caseData.title}</div>
          <div class="case-info">${caseData.court} • ${formatLegalDate(caseData.date)}</div>
          
          <div class="spinner"></div>
          <div class="loading-text">Loading full case opinion...</div>
          
          <div class="skeleton-container">
            <div class="skeleton"></div>
            <div class="skeleton"></div>
            <div class="skeleton"></div>
            <div class="skeleton"></div>
            <div class="skeleton"></div>
            <div class="skeleton"></div>
          </div>
        </div>
      </body>
      </html>
    `);
    
    // 4. Fetch data
    toast({
      title: "Loading document",
      description: "Retrieving case text...",
      variant: "default",
    });
    
    const fullDocument = await fetchFullDocument();
    
    if (fullDocument) {
      // 5. Update the window with content
      previewWindow.document.open();
      previewWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
          <title>${caseData.title} - Document Preview</title>
          <style>
            body { font-family: system-ui, -apple-system, sans-serif; line-height: 1.6; padding: 20px; max-width: 800px; margin: 0 auto; }
            h1 { font-size: 24px; margin-bottom: 16px; }
            .document-content { white-space: pre-wrap; }
            .actions { margin-top: 20px; }
            button { padding: 8px 16px; background: #2563eb; color: white; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background: #1d4ed8; }
          </style>
        </head>
        <body>
          <h1>${caseData.title}</h1>
          <div class="document-content">${fullDocument.content}</div>
          <div class="actions">
            <button onclick="window.print()">Print / Download PDF</button>
          </div>
        </body>
        </html>
      `);
      previewWindow.document.close();
      
      localStorageService.addActivity('view', `Previewed document: ${caseData.title}`, caseId);
    } else {
      // 6. Show error in the popup if fetch failed
      previewWindow.document.open();
      previewWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
          <title>Error Loading Document</title>
          <style>
            body { font-family: system-ui, -apple-system, sans-serif; text-align: center; padding-top: 100px; color: #555; }
            .error { color: #e74c3c; margin: 20px 0; }
          </style>
        </head>
        <body>
          <h2>Error Loading Document</h2>
          <p class="error">Unable to retrieve the document content.</p>
          <p>Please try again later.</p>
        </body>
        </html>
      `);
      previewWindow.document.close();
    }
  }

  // Handle PDF preview
  const handlePreviewPdf = () => {
    console.log("PDF preview - using ID:", caseId, "for case:", caseData.title);

    try {
      // Add debug logging
      console.log("Case data for PDF:", {
        id: caseData.id,
        title: caseData.title,
        court: caseData.court,
        date: caseData.date
      });
      
      // Add a random query parameter to prevent caching
      const timestamp = new Date().getTime();
      // Include all available metadata for accurate case lookup
      const pdfUrl = `/api/v1/case/${caseData.id}/pdf?title=${encodeURIComponent(caseData.title)}&court=${encodeURIComponent(caseData.court)}&date=${encodeURIComponent(caseData.date)}&jurisdiction=${encodeURIComponent(caseData.tags && caseData.tags.length > 0 ? caseData.tags[0] : "")}&nocache=${timestamp}`;
      console.log("Opening PDF with URL:", pdfUrl);
      window.open(pdfUrl, '_blank');
      
      toast({
        title: "PDF preview opened",
        description: "The PDF preview has opened in a new tab.",
        variant: "default",
      });
      
      localStorageService.addActivity('view', `Previewed PDF: ${caseData.title}`, caseId);
    } catch (error) {
      console.error("Error previewing PDF:", error);
      toast({
        title: "Preview failed",
        description: "There was an error opening the PDF preview. Please try again later.",
        variant: "destructive",
      });
    }
  };

  // Handle PDF download
  const handleDownloadPdf = async () => {
    toast({
      title: "Preparing PDF",
      description: "Your PDF is being generated...",
      variant: "default",
    });
  
    try {
      // Build URL with all available metadata for accurate case lookup
      const downloadUrl = `/api/v1/case/${caseId}/pdf?download=true&title=${encodeURIComponent(caseData.title)}&court=${encodeURIComponent(caseData.court)}&date=${encodeURIComponent(caseData.date)}&jurisdiction=${encodeURIComponent(caseData.tags && caseData.tags.length > 0 ? caseData.tags[0] : "")}`;
      
      // Add debug logging
      console.log("Downloading PDF with URL:", downloadUrl);
      
      // Create an invisible iframe to trigger the download
      const iframe = document.createElement('iframe');
      iframe.style.display = 'none';
      iframe.src = downloadUrl;
      document.body.appendChild(iframe);
      
      // Remove the iframe after a moment
      setTimeout(() => {
        document.body.removeChild(iframe);
      }, 2000);
      
      toast({
        title: "Download started",
        description: "Your PDF is being downloaded.",
        variant: "default",
      });
      
      localStorageService.addActivity('export', `Downloaded PDF: ${caseData.title}`, caseId);
    } catch (error) {
      console.error("Error downloading PDF:", error);
      toast({
        title: "Download failed",
        description: "There was an error generating the PDF. Please try again later.",
        variant: "destructive",
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader className="flex justify-between items-start">
          <DialogTitle className="text-xl font-semibold text-secondary-900 dark:text-white pr-8">
            {caseData.title}
          </DialogTitle>
          {/* No duplicate X button */}
        </DialogHeader>
        
        <div className="mb-4 text-sm text-secondary-600 dark:text-secondary-400 font-serif italic">
          {caseData.court} • {formatLegalDate(caseData.date)}
        </div>
        
        {/* Syllabus section with loading state */}
        <div className="mb-6">
          <h3 className="text-lg font-medium text-secondary-900 dark:text-white mb-2">
            Syllabus
          </h3>
          {isLoading ? (
            <SyllabusLoadingState />
          ) : (
            renderSyllabus()
          )}
        </div>

        {/* Key Passages section with loading sensitivity */}
        {!isLoading && caseData.keyPassages && caseData.keyPassages.length > 0 && 
          caseData.keyPassages.some(passage => passage.length >= 70) && (
          <div className="mb-6">
            <h3 className="text-lg font-medium text-secondary-900 dark:text-white mb-2">
              Key Passages
            </h3>
            {caseData.keyPassages
              .filter(passage => passage.length >= 70)
              .map((passage, index) => (
                <blockquote
                  key={index}
                  className="border-l-4 border-primary-600 pl-4 py-1 mb-3 text-sm text-secondary-700 dark:text-secondary-300 italic font-serif"
                >
                  "{highlightKeyTerms(passage)}"
                </blockquote>
              ))}
          </div>
        )}
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div>
            <h3 className="text-lg font-medium text-secondary-900 dark:text-white mb-2">Case Information</h3>
            <div className="text-sm">
              {/* Add Title field at the top */}
              <div className="flex flex-col sm:flex-row justify-between py-2 border-b border-secondary-100 dark:border-secondary-700">
                <span className="text-secondary-500 dark:text-secondary-400 font-medium mb-1 sm:mb-0">Title</span>
                <span className="text-secondary-700 dark:text-secondary-300 sm:text-right sm:ml-4 sm:max-w-[75%]">{caseData.title}</span>
              </div>

              <div className="flex flex-col sm:flex-row justify-between py-2 border-b border-secondary-100 dark:border-secondary-700">
                <span className="text-secondary-500 dark:text-secondary-400 font-medium mb-1 sm:mb-0">Court</span>
                <span className="text-secondary-700 dark:text-secondary-300 sm:text-right sm:ml-4 sm:max-w-[75%]">{caseData.court}</span>
              </div>

              <div className="flex justify-between py-1 border-b border-secondary-100 dark:border-secondary-700">
                <span className="text-secondary-500 dark:text-secondary-400">Date</span>
                <span className="text-secondary-700 dark:text-secondary-300">{formatLegalDate(caseData.date)}</span>
              </div>

              {/* Only show Citations if it exists */}
              {caseData.citation && caseData.citation.trim() && (
                <div className="flex justify-between py-1 border-b border-secondary-100 dark:border-secondary-700">
                  <span className="text-secondary-500 dark:text-secondary-400">Citations</span>
                  <span className="text-secondary-700 dark:text-secondary-300">{caseData.citation}</span>
                </div>
              )}

              {/* Show Judge if available */}
              {caseData.judges && (
                <div className="flex flex-col sm:flex-row justify-between py-2 border-b border-secondary-100 dark:border-secondary-700">
                  <span className="text-secondary-500 dark:text-secondary-400 font-medium mb-1 sm:mb-0">Judge</span>
                  <span className="text-secondary-700 dark:text-secondary-300 sm:text-right sm:ml-4 sm:max-w-[75%]">{caseData.judges}</span>
                </div>
              )}

              <div className="flex justify-between py-1">
                <span className="text-secondary-500 dark:text-secondary-400">Jurisdiction</span>
                <span className="text-secondary-700 dark:text-secondary-300">
                  {caseData.tags && caseData.tags.length > 0 ? caseData.tags[0] : "Unknown"}
                </span>
              </div>
            </div>
          </div>
        </div>

        <Separator className="my-4" />
        
        <DialogFooter className="flex-col sm:flex-row justify-between items-center gap-3 pt-4">
          <div className="flex space-x-2 w-full sm:w-auto">
            <Button 
              variant="outline" 
              className="text-primary-700 border-primary-200 bg-primary-50 hover:bg-primary-100 dark:bg-primary-900/30 dark:text-primary-400 dark:hover:bg-primary-900/50 dark:border-primary-900/50" 
              onClick={handleSaveToggle}
            >
              {saved ? (
                <>
                  <BookmarkIcon className="h-4 w-4 mr-2 fill-current" />
                  Saved
                </>
              ) : (
                <>
                  <Bookmark className="h-4 w-4 mr-2" />
                  Save
                </>
              )}
            </Button>
            
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline">
                  <Clipboard className="h-4 w-4 mr-2" />
                  Copy Citation
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem onClick={() => handleCopyCitation('bluebook')}>
                  <FileText className="h-4 w-4 mr-2" />
                  <span>Bluebook format</span>
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleCopyCitation('apa')}>
                  <FileText className="h-4 w-4 mr-2" />
                  <span>APA format</span>
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleCopyCitation('chicago')}>
                  <FileText className="h-4 w-4 mr-2" />
                  <span>Chicago format</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline">
                  <Share2 className="h-4 w-4 mr-2" />
                  Share
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem onClick={handleCopyLink}>
                  <Copy className="h-4 w-4 mr-2" />
                  <span>Copy Link</span>
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleEmailShare}>
                  <Mail className="h-4 w-4 mr-2" />
                  <span>Share via Email</span>
                </DropdownMenuItem>
                {typeof navigator.share === 'function' && (
                  <DropdownMenuItem onClick={handleWebShare}>
                    <Share2 className="h-4 w-4 mr-2" />
                    <span>Share...</span>
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button>
                <DownloadIcon className="h-4 w-4 mr-2" />
                Case Document
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={handlePreviewDocument}>
                <FileText className="h-4 w-4 mr-2" />
                <span>Full Case Opinion</span>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handlePreviewPdf}>
                <FileText className="h-4 w-4 mr-2" />
                <span>Preview PDF</span>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleDownloadPdf}>
                <DownloadIcon className="h-4 w-4 mr-2" />
                <span>Download PDF</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}