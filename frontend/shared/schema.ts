import { z } from "zod";

// Core types for the application
// These types will be used throughout the application but won't be stored in a database

/**
 * Case interface representing a court case
 */
export interface Case {
  id: number;
  title: string;
  citation: string;
  court: string;
  date: string;
  summary: string;
  tags: string[];
  landmark: boolean;
  citationCount: number;
  fullOpinionLength?: number;
  docketNumber?: string;
  vote?: string;
  keyPassages?: string[];
  relatedCases?: RelatedCase[];
  jurisdiction?: string;
  snippet?: string;
}

/**
 * Related case interface for simplified related case data
 */
export interface RelatedCase {
  id: number;
  title: string;
}

/**
 * Search filters interface
 */
export interface SearchFilters {
  courts: string[];
  dateFrom: string | null;
  dateTo: string | null;
  jurisdiction: string;
  caseType?: string;
  citationCount?: {min: number | null, max: number | null};
  opinion?: {judge: string | null, length: {min: number | null, max: number | null}};
  voteType?: string;
  landmark?: boolean;
}

/**
 * Search result interface
 */
export interface SearchResult {
  totalResults: number;
  page: number;
  totalPages: number;
  cases: Case[];
}

/**
 * Sort options enum
 */
export enum SortOption {
  Relevance = "Relevance",
  DateNewest = "Date (newest)",
  DateOldest = "Date (oldest)",
  CitationsMost = "Citations (most)"
}

// Validation schemas
export const searchFiltersSchema = z.object({
  courts: z.array(z.string()),
  dateFrom: z.string().nullable(),
  dateTo: z.string().nullable(),
  jurisdiction: z.string(),
  caseType: z.string().optional(),
  citationCount: z.object({
    min: z.number().nullable().optional(),
    max: z.number().nullable().optional()
  }).optional(),
  opinion: z.object({
    judge: z.string().nullable().optional(),
    length: z.object({
      min: z.number().nullable().optional(),
      max: z.number().nullable().optional()
    })
  }).optional(),
  voteType: z.string().optional(),
  landmark: z.boolean().optional()
});

export const caseSchema = z.object({
  id: z.number(),
  title: z.string(),
  citation: z.string(),
  court: z.string(),
  date: z.string(),
  summary: z.string(),
  tags: z.array(z.string()),
  landmark: z.boolean(),
  citationCount: z.number(),
  fullOpinionLength: z.number().optional(),
  docketNumber: z.string().optional(),
  vote: z.string().optional(),
  keyPassages: z.array(z.string()).optional(),
  relatedCases: z.array(z.object({
    id: z.number(),
    title: z.string()
  })).optional(),
  jurisdiction: z.string().optional(),
  snippet: z.string().optional()
});
