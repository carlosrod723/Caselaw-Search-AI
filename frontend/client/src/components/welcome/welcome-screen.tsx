import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useSearch } from "@/context/search-context";
import { Scale, Search, BookOpen, FileText, ListFilter, GraduationCap } from "lucide-react";

interface ExampleSearchProps {
  query: string;
  description: string;
  onSearch: (query: string) => void;
}

function ExampleSearch({ query, description, onSearch }: ExampleSearchProps) {
  return (
    <button
      onClick={() => onSearch(query)}
      className="flex flex-col items-start text-left p-3 hover:bg-secondary-50 dark:hover:bg-secondary-800 rounded-md transition-colors"
    >
      <div className="flex items-center gap-2">
        <Search className="h-4 w-4 text-primary-500" />
        <span className="font-medium text-secondary-900 dark:text-white">{query}</span>
      </div>
      <p className="mt-1 text-sm text-secondary-500 dark:text-secondary-400 pl-6">
        {description}
      </p>
    </button>
  );
}

interface WelcomeScreenProps {
  onSearch: (query: string) => void;
}

export function WelcomeScreen({ onSearch }: WelcomeScreenProps) {
  const { setSearchQuery } = useSearch();

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    onSearch(query);
  };

  const exampleSearches = [
    {
      query: "first amendment freedom of speech",
      description: "Find key cases on First Amendment protections of free speech",
    },
    {
      query: "Miranda rights",
      description: "Explore landmark cases establishing police procedure requirements",
    },
    {
      query: "patent infringement technology",
      description: "Research intellectual property disputes in technology sector",
    },
    {
      query: "Title VII employment discrimination",
      description: "Discover cases interpreting workplace discrimination laws",
    },
  ];

  return (
    <div className="max-w-4xl mx-auto p-6 animate-in fade-in duration-500">
      <div className="flex flex-col items-center text-center mb-12">
        <div className="bg-primary-50 dark:bg-primary-900/30 p-6 rounded-full mb-6">
          <Scale className="h-16 w-16 text-primary-600 dark:text-primary-400" />
        </div>
        <h1 className="text-3xl md:text-4xl font-bold text-secondary-900 dark:text-white mb-3">
          Welcome to CaseLaw AI
        </h1>
        <p className="text-xl text-secondary-600 dark:text-secondary-300 mb-6">
          Advanced legal research powered by artificial intelligence
        </p>
        <p className="text-secondary-500 dark:text-secondary-400 max-w-3xl">
          Search through 6+ million court decisions using natural language or boolean queries
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-8 mb-10">
        <div className="bg-white dark:bg-secondary-800 border border-secondary-200 dark:border-secondary-700 rounded-lg overflow-hidden shadow-sm">
          <div className="bg-secondary-50 dark:bg-secondary-800 p-4 border-b border-secondary-200 dark:border-secondary-700">
            <h2 className="font-semibold text-secondary-900 dark:text-white flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-primary-500" />
              Search Capabilities
            </h2>
          </div>
          <div className="p-4 space-y-3">
            <div className="flex items-start gap-3">
              <div className="bg-primary-50 dark:bg-primary-900/20 p-1.5 rounded-md mt-0.5">
                <Search className="h-4 w-4 text-primary-500" />
              </div>
              <div>
                <h3 className="font-medium text-secondary-900 dark:text-white">Natural Language</h3>
                <p className="text-sm text-secondary-500 dark:text-secondary-400">
                  Ask questions in plain English to find relevant cases
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="bg-primary-50 dark:bg-primary-900/20 p-1.5 rounded-md mt-0.5">
                <FileText className="h-4 w-4 text-primary-500" />
              </div>
              <div>
                <h3 className="font-medium text-secondary-900 dark:text-white">Citation Search</h3>
                <p className="text-sm text-secondary-500 dark:text-secondary-400">
                  Search by specific citation formats (e.g., 347 U.S. 483)
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="bg-primary-50 dark:bg-primary-900/20 p-1.5 rounded-md mt-0.5">
                <ListFilter className="h-4 w-4 text-primary-500" />
              </div>
              <div>
                <h3 className="font-medium text-secondary-900 dark:text-white">Advanced Filters</h3>
                <p className="text-sm text-secondary-500 dark:text-secondary-400">
                  Filter by court, date range, jurisdiction, and more
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="bg-primary-50 dark:bg-primary-900/20 p-1.5 rounded-md mt-0.5">
                <GraduationCap className="h-4 w-4 text-primary-500" />
              </div>
              <div>
                <h3 className="font-medium text-secondary-900 dark:text-white">Expert Mode</h3>
                <p className="text-sm text-secondary-500 dark:text-secondary-400">
                  Use Boolean operators (AND, OR, NOT) for precision searches
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-secondary-800 border border-secondary-200 dark:border-secondary-700 rounded-lg overflow-hidden shadow-sm">
          <div className="bg-secondary-50 dark:bg-secondary-800 p-4 border-b border-secondary-200 dark:border-secondary-700">
            <h2 className="font-semibold text-secondary-900 dark:text-white flex items-center gap-2">
              <Search className="h-5 w-5 text-primary-500" />
              Try These Searches
            </h2>
          </div>
          <div className="divide-y divide-secondary-100 dark:divide-secondary-700">
            {exampleSearches.map((example, index) => (
              <ExampleSearch
                key={index}
                query={example.query}
                description={example.description}
                onSearch={handleSearch}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}