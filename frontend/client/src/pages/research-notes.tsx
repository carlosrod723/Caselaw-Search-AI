// src/pages/research-notes.tsx
import { useState, useEffect } from "react";
import { PlusCircle, FileText, Calendar, X, Edit, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";

interface ResearchNote {
  id: number;
  title: string;
  content: string;
  date: string;
  lastEdited: string;
}

export default function ResearchNotes() {
  const [notes, setNotes] = useState<ResearchNote[]>([]);
  const [editingNote, setEditingNote] = useState<ResearchNote | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  
  // Load notes from localStorage on component mount
  useEffect(() => {
    const savedNotes = localStorage.getItem('research-notes');
    if (savedNotes) {
      try {
        setNotes(JSON.parse(savedNotes));
      } catch (e) {
        console.error('Failed to parse research notes:', e);
        setNotes([]);
      }
    }
  }, []);
  
  // Save notes to localStorage when they change
  useEffect(() => {
    localStorage.setItem('research-notes', JSON.stringify(notes));
  }, [notes]);
  
  const handleCreateNote = () => {
    const newNote = {
      id: Date.now(),
      title: 'Untitled Note',
      content: '',
      date: new Date().toISOString(),
      lastEdited: new Date().toISOString()
    };
    
    setEditingNote(newNote);
    setIsDialogOpen(true);
  };
  
  const handleEditNote = (note: ResearchNote) => {
    setEditingNote({...note});
    setIsDialogOpen(true);
  };
  
  const handleDeleteNote = (noteId: number) => {
    setNotes(notes.filter(note => note.id !== noteId));
  };
  
  const handleSaveNote = () => {
    if (!editingNote) return;
    
    const updatedNote = {
      ...editingNote,
      lastEdited: new Date().toISOString()
    };
    
    // Check if this is a new note or updating an existing one
    if (notes.some(note => note.id === updatedNote.id)) {
      // Update existing note
      setNotes(notes.map(note => 
        note.id === updatedNote.id ? updatedNote : note
      ));
    } else {
      // Add new note
      setNotes([updatedNote, ...notes]);
    }
    
    setIsDialogOpen(false);
    setEditingNote(null);
  };
  
  const handleChangeTitle = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!editingNote) return;
    setEditingNote({
      ...editingNote,
      title: e.target.value
    });
  };
  
  const handleChangeContent = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    if (!editingNote) return;
    setEditingNote({
      ...editingNote,
      content: e.target.value
    });
  };
  
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric', 
      year: 'numeric' 
    });
  };

  return (
    <>
      <div className="flex-1 overflow-y-auto p-4 lg:p-6">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between mb-4">
          <div>
            <h1 className="text-lg font-semibold text-secondary-900 dark:text-white">Research Notes</h1>
            <p className="text-sm text-secondary-500 dark:text-secondary-400">
              Create and organize notes for your legal research
            </p>
          </div>
          
          <Button 
            onClick={handleCreateNote} 
            className="mt-2 md:mt-0"
          >
            <PlusCircle className="h-4 w-4 mr-2" />
            New Note
          </Button>
        </div>
        
        <Separator className="my-4" />
        
        {notes.length === 0 ? (
          <div className="bg-white dark:bg-secondary-800 rounded-lg shadow-sm border border-secondary-200 dark:border-secondary-700 p-6 text-center">
            <FileText className="h-12 w-12 mx-auto text-secondary-400 mb-3" />
            <h3 className="text-lg font-medium text-secondary-900 dark:text-white mb-1">No Research Notes</h3>
            <p className="text-secondary-600 dark:text-secondary-400 mb-4">
              Create your first research note to get started.
            </p>
            <Button onClick={handleCreateNote}>
              <PlusCircle className="h-4 w-4 mr-2" />
              Create a Note
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {notes.map(note => (
              <div 
                key={note.id} 
                className="bg-white dark:bg-secondary-800 rounded-lg shadow-sm border border-secondary-200 dark:border-secondary-700 overflow-hidden relative"
              >
                <div className="p-4">
                  <div className="flex justify-between items-start">
                    <h3 className="text-lg font-medium text-secondary-900 dark:text-white mb-1 pr-8">
                      {note.title}
                    </h3>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="absolute top-2 right-2 h-8 w-8 text-secondary-500 hover:text-secondary-900 dark:text-secondary-400 dark:hover:text-white"
                      onClick={() => handleDeleteNote(note.id)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                  
                  <div className="text-xs text-secondary-500 dark:text-secondary-400 mb-3 flex items-center">
                    <Calendar className="h-3 w-3 mr-1" />
                    Last edited {formatDate(note.lastEdited)}
                  </div>
                  
                  <p className="text-sm text-secondary-700 dark:text-secondary-300 mb-3 min-h-[3rem] line-clamp-3">
                    {note.content || 'No content yet. Click to edit this note.'}
                  </p>
                  
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="w-full mt-2"
                    onClick={() => handleEditNote(note)}
                  >
                    <Edit className="h-4 w-4 mr-2" />
                    Edit Note
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      
      {/* Edit Note Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold">
              {editingNote?.id ? 'Edit Note' : 'Create Note'}
            </DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label htmlFor="note-title" className="text-sm font-medium text-secondary-900 dark:text-white">
                Title
              </label>
              <Input
                id="note-title"
                value={editingNote?.title || ''}
                onChange={handleChangeTitle}
                placeholder="Enter note title"
                className="w-full"
              />
            </div>
            
            <div className="space-y-2">
              <label htmlFor="note-content" className="text-sm font-medium text-secondary-900 dark:text-white">
                Content
              </label>
              <Textarea
                id="note-content"
                value={editingNote?.content || ''}
                onChange={handleChangeContent}
                placeholder="Enter your notes here..."
                className="min-h-[200px] w-full"
              />
            </div>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveNote}>
              <Save className="h-4 w-4 mr-2" />
              Save Note
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}