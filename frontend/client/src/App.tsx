import { Switch, Route } from "wouter";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/lib/queryClient";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SearchProvider } from "@/context/search-context";
import { MainLayout } from "@/components/layouts/main-layout";

// Pages
import Home from "@/pages/home";
import SearchPage from "@/pages/search";
import SavedCasesPage from "@/pages/saved-cases";
import RecentActivityPage from "@/pages/recent-activity";
import ResearchNotesPage from "@/pages/research-notes"; // Import the new page
import NotFound from "@/pages/not-found";

function Router() {
  return (
    <MainLayout>
      <Switch>
        <Route path="/" component={Home} />
        <Route path="/search" component={SearchPage} />
        <Route path="/saved-cases" component={SavedCasesPage} />
        <Route path="/recent-activity" component={RecentActivityPage} />
        <Route path="/research-notes" component={ResearchNotesPage} /> {/* Add the new route */}
        <Route component={NotFound} />
      </Switch>
    </MainLayout>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <SearchProvider>
        <TooltipProvider>
          <Toaster />
          <Router />
        </TooltipProvider>
      </SearchProvider>
    </QueryClientProvider>
  );
}

export default App;