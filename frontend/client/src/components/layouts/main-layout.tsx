import { useState } from "react";
import { 
  Menu, 
  Moon, 
  Sun, 
  HelpCircle, 
  Home, 
  Gavel, 
  FileText, 
  Landmark, 
  ScrollText, 
  BadgeCheck 
} from "lucide-react"; // Added case type icons
import { Button } from "@/components/ui/button";
import { Sidebar } from "@/components/sidebar/sidebar";
import { SearchBar } from "@/components/search/search-bar";
import { useTheme } from "@/hooks/use-theme";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "@/components/ui/dialog";
import { Link, useLocation } from "wouter"; // Add useLocation
import { Footer } from "./footer";
import { useSearch } from "@/context/search-context"; // Import search context

interface MainLayoutProps {
  children: React.ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  const { theme, toggleTheme } = useTheme();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [location, navigate] = useLocation(); // Get current location and navigation function
  const { setSearchQuery } = useSearch(); // Get search context function
  
  const toggleSidebar = () => {
    setSidebarCollapsed(!sidebarCollapsed);
  };

  // Handle home button click
  const handleHomeClick = () => {
    // Clear the search query
    setSearchQuery("");
    // Navigate to home page
    navigate("/");
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Desktop Sidebar */}
      <Sidebar 
        collapsed={sidebarCollapsed} 
        onToggleCollapse={toggleSidebar} 
        className="hidden lg:flex" 
      />
      
      {/* Main Content Area */}
      <main className="flex-1 flex flex-col h-full overflow-hidden">
        <header className="flex items-center h-[4.5rem] px-4 border-b border-secondary-200 dark:border-secondary-800 bg-white dark:bg-secondary-900 z-10">
          {/* Mobile menu button */}
          <Sheet>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="lg:hidden mr-2 text-secondary-500 hover:text-secondary-700 dark:text-secondary-400 dark:hover:text-secondary-200">
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="p-0 w-72">
              <Sidebar />
            </SheetContent>
          </Sheet>
          
          <SearchBar />
          
          <div className="ml-auto flex items-center">
            {/* Home button - NEW */}
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={handleHomeClick}
              title="Return to home page"
              aria-label="Go to home page"
              className="ml-4 rounded-full p-1 text-secondary-500 hover:bg-secondary-100 dark:text-secondary-400 dark:hover:bg-secondary-800"
            >
              <Home className="h-5 w-5" />
            </Button>
            
            {/* Theme toggle button */}
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={toggleTheme}
              aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
              className="ml-4 rounded-full p-1 text-secondary-500 hover:bg-secondary-100 dark:text-secondary-400 dark:hover:bg-secondary-800"
            >
              <Sun className="h-5 w-5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
              <Moon className="absolute h-5 w-5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
            </Button>
            
            {/* Help button with Dialog */}
            <Dialog>
              <DialogTrigger asChild>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  aria-label="Help and information"
                  className="ml-4 rounded-full p-1 text-secondary-500 hover:bg-secondary-100 dark:text-secondary-400 dark:hover:bg-secondary-800"
                >
                  <HelpCircle className="h-5 w-5" />
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[550px]">
                <DialogHeader>
                  <DialogTitle>CaseLaw AI Help</DialogTitle>
                  <DialogDescription>
                    How to use this legal research tool effectively
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-2 py-1">
                  <div>
                    <h3 className="text-sm font-medium">Search Capabilities</h3>
                    <p className="text-sm text-secondary-500 dark:text-secondary-400">
                      Use natural language queries, citation search, or advanced boolean operators to find relevant cases.
                    </p>
                  </div>
                  
                  <div>
                    <h3 className="text-sm font-medium">Keyboard Shortcuts</h3>
                    <div className="text-sm text-secondary-500 dark:text-secondary-400">
                      <p>⌘K / Ctrl+K: Open search bar</p>
                      <p>Esc: Close dialogs</p>
                    </div>
                  </div>
                  
                  <div>
                    <h3 className="text-sm font-medium">Advanced Filters</h3>
                    <p className="text-sm text-secondary-500 dark:text-secondary-400">
                      After completing a search, use the sidebar filters to narrow your search by court, date range, jurisdiction, and more.
                    </p>
                  </div>
                  
                  <div>
                    <h3 className="text-sm font-medium">Advanced Search Syntax</h3>
                    <p className="text-sm text-secondary-500 dark:text-secondary-400">
                      For precision searches, use Boolean operators (AND, OR, NOT) and quotation marks for exact phrases. Examples: <span className="font-mono text-xs bg-secondary-100 dark:bg-secondary-800 px-1 rounded">copyright AND infringement</span>, <span className="font-mono text-xs bg-secondary-100 dark:bg-secondary-800 px-1 rounded">"fair use" NOT parody</span>
                    </p>
                  </div>
                  
                  <div>
                    <h3 className="text-sm font-medium">Case Types</h3>
                    <div className="space-y-2 mt-2">
                      <div className="flex items-start">
                        <div className="flex-shrink-0 mr-2">
                          <Gavel className="h-4 w-4 text-red-500" />
                        </div>
                        <p className="text-sm text-secondary-500 dark:text-secondary-400">
                          <span className="font-medium">Criminal</span> - Cases involving crimes and prosecutions, including trials, sentencing, and appeals in criminal matters.
                        </p>
                      </div>
                      
                      <div className="flex items-start">
                        <div className="flex-shrink-0 mr-2">
                          <FileText className="h-4 w-4 text-blue-500" />
                        </div>
                        <p className="text-sm text-secondary-500 dark:text-secondary-400">
                          <span className="font-medium">Civil</span> - Disputes between individuals, organizations, or entities, including contract disputes, torts, property rights, and other non-criminal matters.
                        </p>
                      </div>
                      
                      <div className="flex items-start">
                        <div className="flex-shrink-0 mr-2">
                          <Landmark className="h-4 w-4 text-amber-500" />
                        </div>
                        <p className="text-sm text-secondary-500 dark:text-secondary-400">
                          <span className="font-medium">Administrative</span> - Cases involving government agencies, regulatory bodies, and administrative proceedings, including appeals of agency decisions.
                        </p>
                      </div>
                      
                      <div className="flex items-start">
                        <div className="flex-shrink-0 mr-2">
                          <ScrollText className="h-4 w-4 text-green-500" />
                        </div>
                        <p className="text-sm text-secondary-500 dark:text-secondary-400">
                          <span className="font-medium">Constitutional</span> - Cases involving interpretation of the constitution, fundamental rights, government powers, and challenges to legislative or executive actions.
                        </p>
                      </div>
                      
                      <div className="flex items-start">
                        <div className="flex-shrink-0 mr-2">
                          <BadgeCheck className="h-4 w-4 text-purple-500" />
                        </div>
                        <p className="text-sm text-secondary-500 dark:text-secondary-400">
                          <span className="font-medium">Disciplinary</span> - Professional conduct cases including attorney disbarment, judicial discipline, and other matters related to professional licensing and ethics.
                        </p>
                      </div>
                    </div>
                  </div>
                  
                  <div>
                    <h3 className="text-sm font-medium">Database Coverage</h3>
                    <p className="text-sm text-secondary-500 dark:text-secondary-400">
                    CaseLaw AI provides access to over ~6 million court cases spanning from 1662 to 2020, with intelligent ranking to surface the most relevant results first. Our database includes cases from 58 jurisdictions, with significant coverage of US Federal courts, New York, Louisiana, Florida, and Texas. For optimal performance, search results are limited to the top 200 most relevant cases. For more specific results, try refining your search terms or using the advanced filters.
                    </p>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </header>
        
        {/* Page content */}
        <div className="flex-1 overflow-auto">
          {children}
        </div>
        
        {/* Footer */}
        <Footer />
      </main>
    </div>
  );
}