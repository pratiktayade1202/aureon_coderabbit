// src/utils/logger.js

const isDev = import.meta.env.DEV;

/**
 * Sanitize paths by replacing IDs with placeholders
 * Prevents leaking sensitive identifiers in logs
 */
const sanitizePath = (path) => {
    if (!path) return '';
    return path
        .replace(/\/\d+/g, '/:id')
        .replace(/[a-f0-9-]{36}/gi, ':uuid');
};

/**
 * Development-only logger
 * In production, debug/info logs are suppressed
 */
export const logger = {
    debug: (...args) => {
        if (isDev) console.debug('[DEBUG]', ...args);
    },
    info: (...args) => {
        if (isDev) console.info('[INFO]', ...args);
    },
    warn: (...args) => {
        console.warn('[WARN]', ...args);
    },
    error: (...args) => {
        console.error('[ERROR]', ...args);
    },
    api: (method, path) => {
        if (isDev) {
            console.debug(`[API] ${method} ${sanitizePath(path)}`);
        }
    }
};

export default logger;
