// src/utils/fileValidation.js

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
const MAX_FILES_PER_BATCH = 10;

const ALLOWED_TYPES = {
    'text/csv': ['.csv'],
    'application/vnd.ms-excel': ['.xls', '.csv'],
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    'application/pdf': ['.pdf'],
    'application/zip': ['.zip'],
    'application/x-zip-compressed': ['.zip']
};

/**
 * Validate a single file
 * @param {File} file - File object to validate
 * @returns {{ valid: boolean, errors: string[] }}
 */
export const validateFile = (file) => {
    const errors = [];

    // Check file size
    if (file.size > MAX_FILE_SIZE) {
        errors.push(`File too large: ${(file.size / 1024 / 1024).toFixed(1)}MB (max: 50MB)`);
    }

    // Check file extension
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    const allowedExts = Object.values(ALLOWED_TYPES).flat();
    if (!allowedExts.includes(ext)) {
        errors.push(`Invalid file extension: ${ext}`);
    }

    // Validate file name (prevent path traversal)
    if (file.name.includes('..') || file.name.includes('/') || file.name.includes('\\')) {
        errors.push('Invalid file name: contains path traversal characters');
    }

    // Check for suspicious patterns in filename
    if (/\.(exe|bat|cmd|sh|ps1|vbs|js|msi)$/i.test(file.name)) {
        errors.push('Executable files are not allowed');
    }

    return {
        valid: errors.length === 0,
        errors
    };
};

/**
 * Validate a batch of files
 * @param {FileList|File[]} files - Files to validate
 * @returns {{ validFiles: File[], invalidFiles: { name: string, errors: string[] }[], batchError: string|null }}
 */
export const validateFileBatch = (files) => {
    const fileArray = Array.from(files);

    // Check batch size
    if (fileArray.length > MAX_FILES_PER_BATCH) {
        return {
            validFiles: [],
            invalidFiles: [],
            batchError: `Too many files: ${fileArray.length} (maximum ${MAX_FILES_PER_BATCH} files per batch)`
        };
    }

    const validFiles = [];
    const invalidFiles = [];

    fileArray.forEach(file => {
        const validation = validateFile(file);
        if (validation.valid) {
            validFiles.push(file);
        } else {
            invalidFiles.push({ name: file.name, errors: validation.errors });
        }
    });

    return {
        validFiles,
        invalidFiles,
        batchError: null
    };
};

export const FILE_CONFIG = {
    MAX_FILE_SIZE,
    MAX_FILES_PER_BATCH,
    ALLOWED_EXTENSIONS: Object.values(ALLOWED_TYPES).flat()
};
