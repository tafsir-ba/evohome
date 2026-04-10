import { useState, useCallback, useRef } from 'react';
import { Upload, X, ImageIcon, FileIcon, Loader2 } from 'lucide-react';
import { Button } from './ui/button';
import { cn } from '../lib/utils';

/**
 * Drag-and-drop file upload component
 * Supports images and PDFs with preview
 */
export const FileDropZone = ({
  onFileSelect,
  accept = 'image/*,application/pdf',
  maxSizeMB = 10,
  multiple = false,
  className = '',
  disabled = false,
  placeholder = 'Drag & drop files here, or click to browse',
  preview = true,
  children
}) => {
  const [isDragActive, setIsDragActive] = useState(false);
  const [previewFiles, setPreviewFiles] = useState([]);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  const validateFile = (file) => {
    // Check size
    if (file.size > maxSizeMB * 1024 * 1024) {
      return `File "${file.name}" exceeds ${maxSizeMB}MB limit`;
    }

    // Check type
    const acceptTypes = accept.split(',').map(t => t.trim());
    const isValidType = acceptTypes.some(type => {
      if (type.includes('*')) {
        const baseType = type.split('/')[0];
        return file.type.startsWith(baseType);
      }
      return file.type === type;
    });

    if (!isValidType) {
      return `File "${file.name}" is not a supported format`;
    }

    return null;
  };

  const processFiles = useCallback((files) => {
    setError(null);
    const fileList = Array.from(files);
    
    // Validate all files
    for (const file of fileList) {
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        return;
      }
    }

    // Generate previews for images
    if (preview) {
      const newPreviews = fileList.map(file => ({
        file,
        name: file.name,
        type: file.type,
        preview: file.type.startsWith('image/') ? URL.createObjectURL(file) : null
      }));
      setPreviewFiles(multiple ? [...previewFiles, ...newPreviews] : newPreviews);
    }

    // Call parent handler
    onFileSelect(multiple ? fileList : fileList[0]);
  }, [multiple, onFileSelect, preview, previewFiles, maxSizeMB, accept]);

  const handleDragEnter = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled) setIsDragActive(true);
  }, [disabled]);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
  }, []);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);

    if (disabled) return;

    const files = e.dataTransfer?.files;
    if (files?.length > 0) {
      processFiles(files);
    }
  }, [disabled, processFiles]);

  const handleClick = () => {
    if (!disabled) inputRef.current?.click();
  };

  const handleInputChange = (e) => {
    const files = e.target.files;
    if (files?.length > 0) {
      processFiles(files);
    }
    // Reset input for re-selecting same file
    e.target.value = '';
  };

  const removeFile = (index) => {
    const newFiles = previewFiles.filter((_, i) => i !== index);
    setPreviewFiles(newFiles);
    // Notify parent
    onFileSelect(multiple ? newFiles.map(f => f.file) : null);
  };

  const clearAll = () => {
    // Cleanup preview URLs
    previewFiles.forEach(f => {
      if (f.preview) URL.revokeObjectURL(f.preview);
    });
    setPreviewFiles([]);
    onFileSelect(multiple ? [] : null);
  };

  return (
    <div className={cn('space-y-3', className)}>
      {/* Drop Zone */}
      <div
        onClick={handleClick}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        className={cn(
          'relative border-2 border-dashed rounded-lg p-6 transition-all cursor-pointer',
          'hover:border-primary/50 hover:bg-primary/5',
          isDragActive && 'border-primary bg-primary/10',
          disabled && 'opacity-50 cursor-not-allowed',
          error && 'border-destructive',
          !isDragActive && !error && 'border-muted-foreground/25'
        )}
        data-testid="file-drop-zone"
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={handleInputChange}
          className="hidden"
          disabled={disabled}
          data-testid="file-input"
        />

        {children || (
          <div className="flex flex-col items-center justify-center gap-2 text-center">
            <div className={cn(
              'w-12 h-12 rounded-full flex items-center justify-center',
              isDragActive ? 'bg-primary/20 text-primary' : 'bg-muted text-muted-foreground'
            )}>
              <Upload className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-foreground">
                {isDragActive ? 'Drop files here' : placeholder}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Max {maxSizeMB}MB per file
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}

      {/* Preview Grid */}
      {preview && previewFiles.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">
              {previewFiles.length} file{previewFiles.length > 1 ? 's' : ''} selected
            </span>
            {previewFiles.length > 1 && (
              <Button variant="ghost" size="sm" onClick={clearAll} className="h-7 text-xs">
                Clear all
              </Button>
            )}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {previewFiles.map((file, index) => (
              <div
                key={index}
                className="relative group border rounded-lg overflow-hidden bg-muted/50"
              >
                {file.preview ? (
                  <img
                    src={file.preview}
                    alt={file.name}
                    className="w-full h-24 object-cover"
                  />
                ) : (
                  <div className="w-full h-24 flex items-center justify-center">
                    <FileIcon className="w-8 h-8 text-muted-foreground" />
                  </div>
                )}
                <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                  <Button
                    variant="destructive"
                    size="icon"
                    className="h-7 w-7"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeFile(index);
                    }}
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </div>
                <p className="absolute bottom-0 inset-x-0 bg-black/70 text-white text-xs p-1 truncate">
                  {file.name}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default FileDropZone;
