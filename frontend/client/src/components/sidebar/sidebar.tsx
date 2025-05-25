import { useState } from "react";
import { Link, useLocation } from "wouter";
import { Search, Bookmark, History, LibraryBig, ChevronRight, ChevronLeft, Gavel } from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";

interface SidebarProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  className?: string;
}

export function Sidebar({ collapsed = false, onToggleCollapse, className = "" }: SidebarProps) {
  const [location] = useLocation();

  if (collapsed) {
    return (
      <aside className={`lg:flex flex-col w-16 border-r border-secondary-200 dark:border-secondary-800 bg-white dark:bg-secondary-900 transition-all duration-200 ease-in-out ${className}`}>
        <div className="p-4 flex justify-center">
          <div className="w-8 h-8 rounded-md flex items-center justify-center bg-blue-600">
            <Gavel className="h-5 w-5 text-white" />
          </div>
        </div>
        
        <Separator />
        
        <nav className="px-2 py-4 flex-1">
          <ul className="space-y-2">
            <li>
              <Link href="/search">
                <a className={`flex justify-center p-2 rounded-md ${location === "/search" ? "bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400" : "text-secondary-700 hover:bg-secondary-100 dark:text-secondary-300 dark:hover:bg-secondary-800"}`}>
                  <Search className="h-5 w-5" />
                </a>
              </Link>
            </li>
            <li>
              <Link href="/saved-cases">
                <a className={`flex justify-center p-2 rounded-md ${location === "/saved-cases" ? "bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400" : "text-secondary-700 hover:bg-secondary-100 dark:text-secondary-300 dark:hover:bg-secondary-800"}`}>
                  <Bookmark className="h-5 w-5" />
                </a>
              </Link>
            </li>
            <li>
              <Link href="/recent-activity">
                <a className={`flex justify-center p-2 rounded-md ${location === "/recent-activity" ? "bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400" : "text-secondary-700 hover:bg-secondary-100 dark:text-secondary-300 dark:hover:bg-secondary-800"}`}>
                  <History className="h-5 w-5" />
                </a>
              </Link>
            </li>
            <li>
              <Link href="/research-notes">
                <a className={`flex justify-center p-2 rounded-md ${location === "/research-notes" ? "bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400" : "text-secondary-700 hover:bg-secondary-100 dark:text-secondary-300 dark:hover:bg-secondary-800"}`}>
                  <LibraryBig className="h-5 w-5" />
                </a>
              </Link>
            </li>
          </ul>
        </nav>
        
        <div className="p-4 flex justify-center">
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={onToggleCollapse}
            className="text-secondary-500 hover:text-secondary-700 dark:text-secondary-400 dark:hover:text-secondary-200"
          >
            <ChevronRight className="h-5 w-5" />
          </Button>
        </div>
      </aside>
    );
  }

  return (
    <aside className={`hidden lg:flex lg:flex-col w-64 border-r border-secondary-200 dark:border-secondary-800 bg-white dark:bg-secondary-900 overflow-y-auto transition-all duration-200 ease-in-out ${className}`}>
      <div className="p-4 border-b border-secondary-200 dark:border-secondary-800 flex items-center justify-between">
        <div className="flex items-center">
          <div className="w-8 h-8 mr-2 rounded-md flex items-center justify-center bg-blue-600">
            <Gavel className="h-5 w-5 text-white" />
          </div>
          <span className="text-lg font-semibold text-primary-900 dark:text-white">CaseLaw AI</span>
        </div>
        <Button 
          variant="ghost" 
          size="icon" 
          onClick={onToggleCollapse}
          className="text-secondary-500 hover:text-secondary-700 dark:text-secondary-400 dark:hover:text-secondary-200"
        >
          <ChevronLeft className="h-5 w-5" />
        </Button>
      </div>
      
      <div className="p-4">
        <h2 className="text-xs font-semibold uppercase text-secondary-500 dark:text-secondary-400 mb-3">Navigation</h2>
        <nav>
          <ul className="space-y-1">
            <li>
              <Link href="/search">
                <a className={`flex items-center px-3 py-2 text-sm rounded-md ${location === "/search" ? "bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400" : "text-secondary-700 hover:bg-secondary-100 dark:text-secondary-300 dark:hover:bg-secondary-800"}`}>
                  <Search className="h-4 w-4 mr-3" />
                  Search
                </a>
              </Link>
            </li>
            <li>
              <Link href="/saved-cases">
                <a className={`flex items-center px-3 py-2 text-sm rounded-md ${location === "/saved-cases" ? "bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400" : "text-secondary-700 hover:bg-secondary-100 dark:text-secondary-300 dark:hover:bg-secondary-800"}`}>
                  <Bookmark className="h-4 w-4 mr-3" />
                  Saved Cases
                </a>
              </Link>
            </li>
            <li>
              <Link href="/recent-activity">
                <a className={`flex items-center px-3 py-2 text-sm rounded-md ${location === "/recent-activity" ? "bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400" : "text-secondary-700 hover:bg-secondary-100 dark:text-secondary-300 dark:hover:bg-secondary-800"}`}>
                  <History className="h-4 w-4 mr-3" />
                  Recent Activity
                </a>
              </Link>
            </li>
            <li>
              <Link href="/research-notes">
                <a className={`flex items-center px-3 py-2 text-sm rounded-md ${location === "/research-notes" ? "bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400" : "text-secondary-700 hover:bg-secondary-100 dark:text-secondary-300 dark:hover:bg-secondary-800"}`}>
                  <LibraryBig className="h-4 w-4 mr-3" />
                  Research Notes
                </a>
              </Link>
            </li>
          </ul>
        </nav>
      </div>
    </aside>
  );
}