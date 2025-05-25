import { useState, useEffect } from "react";

type Theme = "light" | "dark";

export function useTheme() {
  // Initialize theme state from localStorage or system preference
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window === "undefined") return "light";
    
    const savedTheme = localStorage.getItem("theme") as Theme | null;
    
    if (savedTheme) {
      return savedTheme;
    }
    
    // Check system preference
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  // Effect to handle theme changes and persist to localStorage
  useEffect(() => {
    const root = window.document.documentElement;
    
    root.classList.remove("light", "dark");
    root.classList.add(theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  // Function to toggle theme
  const toggleTheme = () => {
    setTheme(prevTheme => (prevTheme === "light" ? "dark" : "light"));
  };

  return { theme, toggleTheme };
}
