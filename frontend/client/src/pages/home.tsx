import { useEffect } from "react";
import { useLocation } from "wouter";

export default function Home() {
  const [, navigate] = useLocation();

  // Redirect to search page
  useEffect(() => {
    navigate("/search");
  }, [navigate]);

  return null;
}
