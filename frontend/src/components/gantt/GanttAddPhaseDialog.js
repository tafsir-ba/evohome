import { useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';

export const GanttAddPhaseDialog = ({ open, onOpenChange, onConfirm, saving }) => {
  const [name, setName] = useState('');

  const handleConfirm = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    onConfirm(trimmed);
    setName('');
    onOpenChange(false);
  };

  const handleOpenChange = (next) => {
    if (!next) setName('');
    onOpenChange(next);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add phase</DialogTitle>
        </DialogHeader>
        <div className="space-y-2 py-2">
          <Label htmlFor="phase-name">Phase name</Label>
          <Input
            id="phase-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Foundation"
            onKeyDown={(e) => e.key === 'Enter' && handleConfirm()}
            autoFocus
          />
          <p className="text-xs text-muted-foreground">
            Creates a starter task in the new phase.
          </p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={saving || !name.trim()}>
            Add phase
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
