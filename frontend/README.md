# CaseLaw AI Frontend

A modern, responsive web application for legal professionals to search, explore, and analyze case law using semantic search powered by vector embeddings and large language models.

## Technology Stack

### Core Framework
- **React 18**: Utilizing the latest features including concurrent rendering and automatic batching
- **TypeScript**: Full type safety throughout the application
- **Vite**: For fast development and optimized production builds

### UI and Styling
- **Tailwind CSS**: Utility-first CSS framework for rapid UI development
- **ShadCN UI**: High-quality, accessible component library built on Radix UI
- **CSS Modules**: For component-scoped styling where needed

### State Management
- **React Context API**: For global state management (search parameters, user preferences)
- **React Query**: For server state management, caching, and synchronization
- **LocalStorage**: For persisting user preferences and saved cases

### Routing
- **Wouter**: Lightweight (~1KB) routing library for React applications
- **Route-based code splitting**: For optimized loading performance

### Data Fetching
- **React Query**: For data fetching, caching, and automatic refetching
- **Axios**: For HTTP requests with interceptors for error handling
- **Custom API adapter**: Abstraction layer for backend communication

## Directory Structure

```
frontend/
├── client/               # Client-side application code
│   ├── public/           # Static assets served directly
│   └── src/              # Source code
│       ├── assets/       # Static assets processed by build tools
│       ├── components/   # Reusable UI components
│       │   ├── case-detail/  # Case detail related components
│       │   ├── layouts/      # Layout components
│       │   ├── search/       # Search-related components
│       │   ├── sidebar/      # Sidebar navigation
│       │   ├── ui/           # Base UI components
│       │   └── welcome/      # Welcome screen components
│       ├── context/      # React context providers
│       ├── hooks/        # Custom React hooks
│       ├── lib/          # Utility functions and services
│       │   └── utils/    # Helper utilities
│       ├── pages/        # Page-level components
│       └── types/        # TypeScript type definitions
├── server/               # Optional server-side code for SSR (if used)
└── shared/               # Code shared between client and server
```

## Key Components

### Search Functionality

The search system consists of several interconnected components:

- **`<SearchBar />`**: Main input for natural language queries with autocomplete
- **`<Filters />`**: Advanced filtering options for jurisdictions, courts, case types, and date ranges
- **`<SearchResults />`**: Display of search results with optimized rendering for large result sets
- **`<Pagination />`**: Navigation through paginated search results
- **`<ResultCard />`**: Individual case result display with key metadata

```tsx
// Example: Using the search components
<SearchBar onSearch={handleSearch} />
<Filters 
  jurisdictions={availableJurisdictions} 
  caseTypes={availableCaseTypes}
  onFilterChange={handleFilterChange} 
/>
<SearchResults results={searchResults} />
<Pagination 
  currentPage={page} 
  totalPages={totalPages} 
  onPageChange={setPage} 
/>
```

### Case Details

- **`<CaseDetailDialog />`**: Modal dialog for displaying comprehensive case information
- **Key passages highlighting**: Identification and emphasis of the most relevant passages
- **Citation parsing**: Automatic detection and formatting of legal citations
- **Metadata display**: Structured display of case metadata (court, date, jurisdiction, etc.)

### Navigation and Layout

- **`<Sidebar />`**: Main navigation component with links to different sections
- **`<MainLayout />`**: Page layout wrapper with proper spacing and structure
- **`<Footer />`**: Application footer with relevant links and information

### Theme Support

The application supports both light and dark themes through:

- **`useTheme` hook**: Custom hook for theme management
- **Tailwind dark mode**: Integration with Tailwind's dark mode for consistent styling
- **User preference persistence**: Remembers user's theme preference across sessions

```tsx
// Example: Using the theme hook
const { theme, setTheme } = useTheme();

return (
  <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
    Toggle {theme === 'dark' ? 'Light' : 'Dark'} Mode
  </button>
);
```

### Caching Implementation

Performance is enhanced through strategic caching:

- **React Query caching**: Automatic caching of API responses
- **`caseEnhancementCache.ts`**: Custom cache for expensive case enhancement operations
- **LocalStorage persistence**: Long-term storage of frequently accessed data
- **Debounced search**: Prevention of excessive API calls during typing

## Local Development

### Prerequisites

- Node.js 18.x or higher
- npm 8.x or higher
- Access to the CaseLaw AI backend API (running locally or remotely)

### Installation

1. Clone the repository (if not already done):
   ```bash
   git clone https://github.com/yourusername/caselaw-ai.git
   cd caselaw-ai/frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Create a `.env.local` file for environment variables:
   ```
   VITE_API_BASE_URL=http://localhost:8000
   VITE_DEFAULT_RESULTS_PER_PAGE=10
   ```

4. Start the development server:
   ```bash
   npm run dev
   ```

### Available Scripts

- `npm run dev`: Start development server
- `npm run build`: Build production-ready assets
- `npm run preview`: Preview production build locally
- `npm run lint`: Lint code using ESLint
- `npm run lint:fix`: Automatically fix linting issues
- `npm run typecheck`: Check TypeScript types
- `npm test`: Run tests (if implemented)

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_BASE_URL` | Base URL for backend API requests | `http://localhost:8000` |
| `VITE_DEFAULT_RESULTS_PER_PAGE` | Default number of results per page | `10` |
| `VITE_ENABLE_MOCK_API` | Enable mock API responses for development | `false` |
| `VITE_DEBUG_MODE` | Enable debug logging | `false` |

### Testing

Run tests with:

```bash
npm test
```

For specific test files:

```bash
npm test -- --testPathPattern=search
```

## Performance Optimizations

The frontend implements several performance optimizations:

1. **Code splitting**: Lazy loading of components and routes
2. **Virtualized lists**: For rendering large result sets efficiently
3. **Memoization**: Strategic use of `useMemo` and `useCallback` for expensive operations
4. **Debounced inputs**: Prevention of excessive API calls during user input
5. **Strategic caching**: Both client-side and with React Query
6. **Image optimization**: Proper sizing and lazy loading of images
7. **Web Vitals monitoring**: Runtime tracking of performance metrics

## Browser Compatibility

CaseLaw AI frontend supports the following browsers:

- Chrome/Edge (latest 2 versions)
- Firefox (latest 2 versions)
- Safari (latest 2 versions)

Mobile browsers are supported on:
- iOS Safari (latest 2 versions)
- Android Chrome (latest 2 versions)

## Contributing

Contributions are welcome! Please see the main project README for contribution guidelines.