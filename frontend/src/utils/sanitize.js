// src/utils/sanitize.js
import DOMPurify from 'dompurify';

/**
 * Sanitize text by stripping all HTML tags
 * @param {string} text - Raw text that may contain HTML
 * @returns {string} - Sanitized plain text
 */
export const sanitizeText = (text) => {
    if (!text) return '';
    return DOMPurify.sanitize(String(text), {
        ALLOWED_TAGS: [],
        ALLOWED_ATTR: []
    });
};

/**
 * Sanitize and truncate text
 * @param {string} text - Raw text
 * @param {number} maxLength - Maximum length
 * @returns {string} - Sanitized and truncated text
 */
export const truncateText = (text, maxLength = 160) => {
    const sanitized = sanitizeText(text);
    return sanitized.length > maxLength
        ? sanitized.slice(0, maxLength) + '...'
        : sanitized;
};
