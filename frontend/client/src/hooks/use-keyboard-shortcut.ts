import { useEffect } from "react";

type KeyboardKey = string;
type Modifiers = {
  ctrl?: boolean;
  alt?: boolean;
  shift?: boolean;
  meta?: boolean;
};

export function useKeyboardShortcut(
  key: KeyboardKey,
  callback: () => void,
  modifiers: Modifiers = {}
) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Check if the key matches
      const keyMatches = event.key.toLowerCase() === key.toLowerCase();
      
      // Check if the required modifiers match
      const modifiersMatch = 
        (modifiers.ctrl ? event.ctrlKey : !event.ctrlKey || !modifiers.hasOwnProperty('ctrl')) &&
        (modifiers.alt ? event.altKey : !event.altKey || !modifiers.hasOwnProperty('alt')) &&
        (modifiers.shift ? event.shiftKey : !event.shiftKey || !modifiers.hasOwnProperty('shift')) &&
        (modifiers.meta ? event.metaKey : !event.metaKey || !modifiers.hasOwnProperty('meta'));
      
      // If both key and modifiers match, execute the callback
      if (keyMatches && modifiersMatch) {
        event.preventDefault();
        callback();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    
    // Cleanup
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [key, callback, modifiers]);
}
