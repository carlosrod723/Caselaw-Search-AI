import { useState, useEffect } from "react";
import { SearchResults } from "@/components/search/search-results";
import { WelcomeScreen } from "@/components/welcome/welcome-screen";
import { useSearch } from "@/context/search-context";

export default function SearchPage() {
  const { searchQuery, setSearchQuery } = useSearch();
  const [hasSearched, setHasSearched] = useState(false);

  // Check if there's an active search
  useEffect(() => {
    setHasSearched(searchQuery.length > 0);
  }, [searchQuery]);

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    setHasSearched(true);
  };

  return (
    <>
      {hasSearched ? (
        <SearchResults />
      ) : (
        <WelcomeScreen onSearch={handleSearch} />
      )}
    </>
  );
}
