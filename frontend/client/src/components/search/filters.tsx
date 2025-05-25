import { useState } from "react";
import { 
  FilterIcon, 
  PlusCircle, 
  MinusCircle, 
  ChevronDown, 
  ChevronUp, 
  Gavel,
  BookOpen,
  FilterX
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SearchFilters } from "@/types/case";
import { useSearch } from "@/context/search-context";
import { Badge } from "@/components/ui/badge";

// Default empty filters object
const emptyFilters: SearchFilters = {
  courts: [],  // Keep this for backward compatibility if needed
  court: "all",  // Add this new field for dropdown selection
  dateFrom: null,
  dateTo: null,
  jurisdiction: "all",
  caseType: "all"
};

// Updated courts filter to use a dropdown instead of checkboxes
const courtOptions = [
  { value: "all", label: "All Courts" },
  // Federal Courts
  { value: "Supreme Court of the United States", label: "Supreme Court of the United States" },
  { value: "United States Court of Appeals for the Ninth Circuit", label: "U.S. Court of Appeals (9th Cir.)" },
  { value: "United States Court of Appeals for the Fifth Circuit", label: "U.S. Court of Appeals (5th Cir.)" },
  { value: "United States Court of Appeals for the Fourth Circuit", label: "U.S. Court of Appeals (4th Cir.)" },
  { value: "United States Court of Appeals for the Second Circuit", label: "U.S. Court of Appeals (2nd Cir.)" },
  { value: "United States Court of Appeals for the Eighth Circuit", label: "U.S. Court of Appeals (8th Cir.)" },
  { value: "United States Court of Appeals for the Sixth Circuit", label: "U.S. Court of Appeals (6th Cir.)" },
  { value: "United States Court of Appeals for the Seventh Circuit", label: "U.S. Court of Appeals (7th Cir.)" },
  { value: "United States Court of Appeals for the Third Circuit", label: "U.S. Court of Appeals (3rd Cir.)" },
  { value: "United States Court of Appeals for the Tenth Circuit", label: "U.S. Court of Appeals (10th Cir.)" },
  { value: "United States Court of Appeals for the Eleventh Circuit", label: "U.S. Court of Appeals (11th Cir.)" },
  { value: "United States District Court for the Southern District of New York", label: "U.S. Dist. Court (S.D.N.Y.)" },
  
  // New York Courts
  { value: "New York Supreme Court, Appellate Division", label: "NY Supreme Court, App. Div." },
  { value: "New York Court of Appeals", label: "NY Court of Appeals" },
  { value: "New York Supreme Court", label: "NY Supreme Court" },
  { value: "New York Supreme Court, General Term", label: "NY Supreme Court, Gen. Term" },
  
  // State Supreme Courts
  { value: "Louisiana Supreme Court", label: "Louisiana Supreme Court" },
  { value: "Supreme Court of Georgia", label: "Georgia Supreme Court" },
  { value: "Supreme Court of Pennsylvania", label: "Pennsylvania Supreme Court" },
  { value: "Supreme Court of Ohio", label: "Ohio Supreme Court" },
  { value: "Supreme Court of North Carolina", label: "North Carolina Supreme Court" },
  { value: "Supreme Court of California", label: "California Supreme Court" },
  { value: "Supreme Court of Missouri", label: "Missouri Supreme Court" },
  { value: "Supreme Court of Indiana", label: "Indiana Supreme Court" },
  { value: "Florida Supreme Court", label: "Florida Supreme Court" },
  { value: "Illinois Supreme Court", label: "Illinois Supreme Court" },
  { value: "Washington Supreme Court", label: "Washington Supreme Court" },
  { value: "Wisconsin Supreme Court", label: "Wisconsin Supreme Court" },
  
  // State Appellate Courts
  { value: "Florida District Court of Appeal", label: "Florida Dist. Court of Appeal" },
  { value: "Louisiana Court of Appeal", label: "Louisiana Court of Appeal" },
  { value: "Illinois Appellate Court", label: "Illinois Appellate Court" },
  { value: "Court of Appeals of Georgia", label: "Georgia Court of Appeals" },
  { value: "Missouri Court of Appeals", label: "Missouri Court of Appeals" },
  { value: "Texas Courts of Civil Appeals", label: "Texas Courts of Civil Appeals" },
  { value: "Texas Courts of Appeals", label: "Texas Courts of Appeals" },
  { value: "Texas Court of Criminal Appeals", label: "Texas Court of Criminal Appeals" },
  { value: "Superior Court of Pennsylvania", label: "Pennsylvania Superior Court" },
  { value: "Washington Court of Appeals", label: "Washington Court of Appeals" },
  { value: "Ohio Court of Appeals", label: "Ohio Court of Appeals" },
  { value: "Court of Appeal of the State of California", label: "California Court of Appeal" },
  { value: "District Court of Appeal of the State of California", label: "California Dist. Court of Appeal" },
  
  // Add other top courts as needed
];

// Common jurisdiction options based on data analysis
const jurisdictionOptions = [
  { value: "all", label: "All Jurisdictions" },
  { value: "United States", label: "United States" },
  { value: "New York", label: "New York" },
  { value: "Louisiana", label: "Louisiana" },
  { value: "Florida", label: "Florida" },
  { value: "Texas", label: "Texas" },
  { value: "Pennsylvania", label: "Pennsylvania" },
  { value: "Georgia", label: "Georgia" },
  { value: "Illinois", label: "Illinois" },
  { value: "California", label: "California" },
  { value: "Missouri", label: "Missouri" },
  { value: "Ohio", label: "Ohio" },
  { value: "North Carolina", label: "North Carolina" },
  { value: "Washington", label: "Washington" },
  { value: "New Jersey", label: "New Jersey" },
  { value: "Indiana", label: "Indiana" },
  { value: "Massachusetts", label: "Massachusetts" },
  { value: "Kentucky", label: "Kentucky" },
  { value: "Michigan", label: "Michigan" },
  { value: "Oklahoma", label: "Oklahoma" },
  { value: "Arkansas", label: "Arkansas" },
  { value: "Mississippi", label: "Mississippi" },
  { value: "Iowa", label: "Iowa" },
  { value: "Minnesota", label: "Minnesota" },
  { value: "Oregon", label: "Oregon" },
  { value: "Kansas", label: "Kansas" },
  { value: "Wisconsin", label: "Wisconsin" },
  { value: "Connecticut", label: "Connecticut" },
  { value: "Maryland", label: "Maryland" },
  { value: "South Carolina", label: "South Carolina" },
  { value: "Virginia", label: "Virginia" },
  { value: "Nebraska", label: "Nebraska" },
  { value: "Tennessee", label: "Tennessee" },
  { value: "Colorado", label: "Colorado" },
  { value: "Puerto Rico", label: "Puerto Rico" },
  { value: "District of Columbia", label: "District of Columbia" },
  { value: "Arizona", label: "Arizona" },
  { value: "West Virginia", label: "West Virginia" },
  { value: "Maine", label: "Maine" },
  { value: "Montana", label: "Montana" },
  { value: "Rhode Island", label: "Rhode Island" },
  { value: "Utah", label: "Utah" },
  { value: "Vermont", label: "Vermont" },
  { value: "New Hampshire", label: "New Hampshire" },
  { value: "Idaho", label: "Idaho" },
  { value: "New Mexico", label: "New Mexico" },
  { value: "North Dakota", label: "North Dakota" },
  { value: "South Dakota", label: "South Dakota" },
  { value: "Delaware", label: "Delaware" },
  { value: "Wyoming", label: "Wyoming" },
  { value: "Hawaii", label: "Hawaii" }
];

// Case type options (derived from keyword analysis)
const caseTypeOptions = [
  { value: "all", label: "All Types" },
  { value: "criminal", label: "Criminal" },
  { value: "civil", label: "Civil" },
  { value: "constitutional", label: "Constitutional" },
  { value: "administrative", label: "Administrative" },
  { value: "disciplinary", label: "Disciplinary" } 
];

// Helper to count active filters
function countActiveFilters(filters: SearchFilters): number {
  let count = 0;
  
  // Count courts filter (either the array or single value)
  if (filters.courts && filters.courts.length > 0) count++;
  else if (filters.court && filters.court !== "all") count++;
  
  if (filters.dateFrom !== null) count++;
  if (filters.dateTo !== null) count++;
  if (filters.jurisdiction !== "all") count++;
  if (filters.caseType !== "all") count++;
  
  return count;
}

// Shared filter renderer component to avoid duplicate code
function FilterRenderer({
  localFilters,
  setLocalFilters,
  mobile = false,
}: {
  localFilters: SearchFilters;
  setLocalFilters: React.Dispatch<React.SetStateAction<SearchFilters>>;
  mobile?: boolean;
}) {
  const prefix = mobile ? "mobile-" : "";
  
  return (
    <div className="py-4 space-y-6">
      <Accordion type="multiple" defaultValue={mobile ? undefined : ['date', 'jurisdiction', 'court', 'caseType']}>
        <AccordionItem value="date" className="border-b border-secondary-200 dark:border-secondary-700">
          <AccordionTrigger className="text-sm font-medium text-secondary-700 dark:text-secondary-300">
            Date Range
          </AccordionTrigger>
          <AccordionContent>
            <div className="grid grid-cols-2 gap-2 pt-2">
              <div>
                <Label 
                  htmlFor={`${prefix}date-from`}
                  className="text-xs text-secondary-500 dark:text-secondary-400"
                >
                  From
                </Label>
                <Input 
                  type="date" 
                  id={`${prefix}date-from`}
                  value={localFilters.dateFrom || ""}
                  onChange={(e) => setLocalFilters(prev => ({ ...prev, dateFrom: e.target.value || null }))}
                  className="w-full text-sm rounded dark:bg-secondary-800" 
                  min="1662-01-01"
                  max="2020-07-30"
                />
              </div>
              <div>
                <Label 
                  htmlFor={`${prefix}date-to`}
                  className="text-xs text-secondary-500 dark:text-secondary-400"
                >
                  To
                </Label>
                <Input 
                  type="date" 
                  id={`${prefix}date-to`}
                  value={localFilters.dateTo || ""}
                  onChange={(e) => setLocalFilters(prev => ({ ...prev, dateTo: e.target.value || null }))}
                  className="w-full text-sm rounded dark:bg-secondary-800"
                  min="1662-01-01" 
                  max="2020-07-30"
                />
              </div>
            </div>
          </AccordionContent>
        </AccordionItem>
        
        <AccordionItem value="jurisdiction" className="border-b border-secondary-200 dark:border-secondary-700">
          <AccordionTrigger className="text-sm font-medium text-secondary-700 dark:text-secondary-300">
            Jurisdiction
          </AccordionTrigger>
          <AccordionContent>
            <div className="pt-2">
              <Select 
                value={localFilters.jurisdiction} 
                onValueChange={(value) => setLocalFilters(prev => ({ ...prev, jurisdiction: value }))}
              >
                <SelectTrigger className="w-full text-sm dark:bg-secondary-800">
                  <SelectValue placeholder="Select jurisdiction" />
                </SelectTrigger>
                <SelectContent className="max-h-80">
                  {jurisdictionOptions.map(option => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </AccordionContent>
        </AccordionItem>
        
        <AccordionItem value="court" className="border-b border-secondary-200 dark:border-secondary-700">
          <AccordionTrigger className="text-sm font-medium text-secondary-700 dark:text-secondary-300">
            Court
          </AccordionTrigger>
          <AccordionContent>
            <div className="pt-2">
              <Select 
                value={localFilters.court || "all"} 
                onValueChange={(value) => {
                  // When a court is selected, update both court and courts fields for compatibility
                  if (value === "all") {
                    setLocalFilters(prev => ({ 
                      ...prev, 
                      court: "all",
                      courts: [] 
                    }));
                  } else {
                    setLocalFilters(prev => ({ 
                      ...prev, 
                      court: value,
                      courts: [value]  // For backwards compatibility
                    }));
                  }
                }}
              >
                <SelectTrigger className="w-full text-sm dark:bg-secondary-800">
                  <SelectValue placeholder="Select court" />
                </SelectTrigger>
                <SelectContent className="max-h-80">
                  {courtOptions.map(option => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </AccordionContent>
        </AccordionItem>
        
        <AccordionItem value="caseType" className="border-b-0">
          <AccordionTrigger className="text-sm font-medium text-secondary-700 dark:text-secondary-300">
            Case Type
          </AccordionTrigger>
          <AccordionContent>
            <div className="pt-2">
              <Select 
                value={localFilters.caseType} 
                onValueChange={(value) => setLocalFilters(prev => ({ ...prev, caseType: value }))}
              >
                <SelectTrigger className="w-full text-sm dark:bg-secondary-800">
                  <SelectValue placeholder="Select case type" />
                </SelectTrigger>
                <SelectContent>
                  {caseTypeOptions.map(option => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
}

// Mobile filters component
export function MobileFilters() {
  const { filters, setFilters } = useSearch();
  const [localFilters, setLocalFilters] = useState<SearchFilters>({...filters});
  const [open, setOpen] = useState(false);
  
  const activeFilterCount = countActiveFilters(filters);

  const applyFilters = () => {
    setFilters(localFilters);
    setOpen(false);
  };

  const resetFilters = () => {
    setLocalFilters({...emptyFilters});
    setFilters({...emptyFilters});
    setOpen(false);
  };

  return (
    <div className="lg:hidden mb-4">
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger asChild>
          <Button 
            variant="outline" 
            className="w-full bg-white dark:bg-secondary-800 border border-secondary-300 dark:border-secondary-700 text-secondary-700 dark:text-secondary-300"
          >
            <FilterIcon className="h-4 w-4 mr-2" />
            Filters {activeFilterCount > 0 && (
              <Badge variant="outline" className="ml-2 text-xs">
                {activeFilterCount}
              </Badge>
            )}
          </Button>
        </DialogTrigger>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Search Filters</DialogTitle>
            <DialogDescription>
              Refine your search results with the filters below.
            </DialogDescription>
          </DialogHeader>
          
          <FilterRenderer localFilters={localFilters} setLocalFilters={setLocalFilters} mobile={true} />
          
          <DialogFooter className="flex flex-col space-y-2 sm:space-y-0 sm:flex-row">
            <Button variant="outline" onClick={resetFilters} className="sm:mr-2">
              <FilterX className="h-4 w-4 mr-2" />
              Reset All
            </Button>
            <Button onClick={applyFilters}>
              Apply Filters
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// Desktop filters component
export function DesktopFilters() {
  const { filters, setFilters } = useSearch();
  const [localFilters, setLocalFilters] = useState<SearchFilters>({...filters});
  
  const applyFilters = () => {
    setFilters(localFilters);
  };

  const resetFilters = () => {
    setLocalFilters({...emptyFilters});
    setFilters({...emptyFilters});
  };
  
  return (
    <div className="hidden lg:block w-64 flex-shrink-0 pr-4">
      <div className="sticky top-[80px]">
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-lg font-medium flex justify-between items-center">
              <span>Filters</span>
              {countActiveFilters(filters) > 0 && (
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={resetFilters}
                  className="h-8 px-2 text-secondary-500"
                >
                  <FilterX className="h-4 w-4 mr-1" />
                  Reset
                </Button>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 pt-0">
            <FilterRenderer localFilters={localFilters} setLocalFilters={setLocalFilters} />
          </CardContent>
          <CardFooter className="px-4 py-3 border-t border-secondary-100 dark:border-secondary-800">
            <Button 
              onClick={applyFilters} 
              className="w-full"
            >
              Apply Filters
            </Button>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}

// Advanced query builder for boolean searches
export function QueryBuilder() {
  const { searchQuery, setSearchQuery } = useSearch();
  const [open, setOpen] = useState(false);
  const [localQuery, setLocalQuery] = useState("");
  const [queryParts, setQueryParts] = useState<{term: string, operator: string}[]>([]);
  
  // Initialize on open
  const handleOpen = (open: boolean) => {
    if (open) {
      setLocalQuery(searchQuery);
      // Parse existing query to populate the builder
      const parts = parseQuery(searchQuery);
      setQueryParts(parts);
    }
    setOpen(open);
  };
  
  // Simple query parser
  const parseQuery = (query: string) => {
    // This is a very basic parser - a real one would be more sophisticated
    const parts: {term: string, operator: string}[] = [];
    
    if (!query.trim()) return parts;
    
    // Handle quoted terms
    const regex = /"([^"]+)"|(\S+)/g;
    const terms = [];
    let match;
    
    while ((match = regex.exec(query)) !== null) {
      terms.push(match[1] || match[2]);
    }
    
    // Try to identify operators - very basic approach
    terms.forEach((term, i) => {
      const lowerTerm = term.toLowerCase();
      
      if (lowerTerm === 'and' || lowerTerm === 'or' || lowerTerm === 'not') {
        if (i > 0) {
          parts[parts.length - 1].operator = lowerTerm;
        }
      } else {
        parts.push({
          term,
          operator: i < terms.length - 1 ? 'and' : ''
        });
      }
    });
    
    return parts;
  };
  
  // Build query string from parts
  const buildQuery = () => {
    let query = '';
    
    queryParts.forEach((part, i) => {
      if (i > 0 && part.operator) {
        query += ` ${part.operator.toUpperCase()} `;
      }
      
      // Add quotes around terms with spaces
      const term = part.term.includes(' ') ? `"${part.term}"` : part.term;
      query += term;
    });
    
    return query;
  };
  
  // Add new term
  const addTerm = () => {
    setQueryParts([...queryParts, { term: '', operator: 'and' }]);
  };
  
  // Remove term
  const removeTerm = (index: number) => {
    const newParts = [...queryParts];
    newParts.splice(index, 1);
    setQueryParts(newParts);
  };
  
  // Update term
  const updateTerm = (index: number, term: string) => {
    const newParts = [...queryParts];
    newParts[index].term = term;
    setQueryParts(newParts);
  };
  
  // Update operator
  const updateOperator = (index: number, operator: string) => {
    const newParts = [...queryParts];
    newParts[index].operator = operator;
    setQueryParts(newParts);
  };
  
  // Apply the built query
  const applyQuery = () => {
    const builtQuery = buildQuery();
    setSearchQuery(builtQuery);
    setOpen(false);
  };
  
  return (
    <Popover open={open} onOpenChange={handleOpen}>
      <PopoverTrigger asChild>
        <Button 
          variant="outline" 
          size="sm" 
          className="h-8 text-secondary-700 dark:text-secondary-300 border-secondary-300 dark:border-secondary-700"
        >
          <PlusCircle className="h-3.5 w-3.5 mr-1" />
          Query Builder
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[340px] p-0" align="start">
        <Card className="border-0">
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-sm font-medium">Advanced Boolean Search</CardTitle>
            <CardDescription className="text-xs">
              Build complex search queries with boolean operators
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 space-y-4">
            {queryParts.length === 0 ? (
              <div className="text-center py-4">
                <Gavel className="h-8 w-8 mx-auto text-secondary-400" />
                <p className="text-secondary-500 dark:text-secondary-400 text-sm mt-2">
                  Add search terms to build your query
                </p>
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={addTerm}
                  className="mt-3"
                >
                  <PlusCircle className="h-3.5 w-3.5 mr-1" />
                  Add First Term
                </Button>
              </div>
            ) : (
              <>
                {queryParts.map((part, index) => (
                  <div key={index} className="space-y-2">
                    <div className="flex items-center">
                      {index > 0 && (
                        <Select 
                          value={part.operator} 
                          onValueChange={(value) => updateOperator(index, value)}
                        >
                          <SelectTrigger className="w-20 mr-2 h-8 text-xs">
                            <SelectValue placeholder="AND" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="and">AND</SelectItem>
                            <SelectItem value="or">OR</SelectItem>
                            <SelectItem value="not">NOT</SelectItem>
                          </SelectContent>
                        </Select>
                      )}
                      <div className="flex-1 flex items-center">
                        <Input 
                          value={part.term}
                          onChange={(e) => updateTerm(index, e.target.value)}
                          placeholder="Enter search term"
                          className="flex-1 text-sm h-8"
                        />
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          onClick={() => removeTerm(index)}
                          className="ml-1 h-8 w-8 p-0"
                        >
                          <MinusCircle className="h-4 w-4 text-secondary-500" />
                        </Button>
                      </div>
                    </div>
                    {index < queryParts.length - 1 && (
                      <div className="border-b border-dashed border-secondary-200 dark:border-secondary-700 my-2"></div>
                    )}
                  </div>
                ))}
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={addTerm}
                  className="w-full mt-2"
                >
                  <PlusCircle className="h-3.5 w-3.5 mr-1" />
                  Add Term
                </Button>
              </>
            )}
          </CardContent>
          <CardFooter className="flex justify-between p-4 border-t border-secondary-100 dark:border-secondary-800">
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <Button 
              size="sm" 
              onClick={applyQuery}
              disabled={queryParts.length === 0 || queryParts.some(p => !p.term)}
            >
              Apply Query
            </Button>
          </CardFooter>
        </Card>
      </PopoverContent>
    </Popover>
  );
}