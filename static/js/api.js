/**
 * API wrapper for AJAX calls
 */

const API = {
    baseUrl: '/api',

    /**
     * Generic fetch wrapper with error handling
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, config);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || `HTTP error! status: ${response.status}`);
            }

            return data;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },

    /**
     * GET request
     */
    async get(endpoint, params = {}) {
        const query = new URLSearchParams(params).toString();
        const url = query ? `${endpoint}?${query}` : endpoint;
        return this.request(url, { method: 'GET' });
    },

    /**
     * POST request
     */
    async post(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    /**
     * PUT request
     */
    async put(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    /**
     * DELETE request
     */
    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    },

    // Invoice endpoints
    invoices: {
        getAll: (searchQuery = '') => API.get('/invoices', { search: searchQuery }),
        getById: (id) => API.get(`/invoices/${id}`),
        update: (id, data) => API.put(`/invoices/${id}`, data),
        delete: (id) => API.delete(`/invoices/${id}`),
        getStatistics: () => API.get('/invoices/statistics'),
    },

    // Upload endpoints
    upload: {
        async files(files, onProgress) {
            const formData = new FormData();
            files.forEach(file => formData.append('files[]', file));

            const xhr = new XMLHttpRequest();

            return new Promise((resolve, reject) => {
                xhr.upload.addEventListener('progress', (e) => {
                    if (e.lengthComputable && onProgress) {
                        const percentComplete = (e.loaded / e.total) * 100;
                        onProgress(percentComplete);
                    }
                });

                xhr.addEventListener('load', () => {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        resolve(JSON.parse(xhr.responseText));
                    } else {
                        reject(new Error(xhr.statusText));
                    }
                });

                xhr.addEventListener('error', () => reject(new Error('Upload failed')));
                xhr.addEventListener('abort', () => reject(new Error('Upload aborted')));

                xhr.open('POST', `${API.baseUrl}/upload`);
                xhr.send(formData);
            });
        }
    },

    // Export endpoints
    export: {
        toExcel: () => {
            window.location.href = `${API.baseUrl}/export/excel`;
        },
        toCSV: () => {
            window.location.href = `${API.baseUrl}/export/csv`;
        }
    },

    // Email endpoints
    email: {
        import: (options) => API.post('/email/import', options),
        test: (settings) => API.post('/email/test', settings),
        getSettings: () => API.get('/email/settings'),
        saveSettings: (settings) => API.post('/email/settings', settings),
        getFolders: () => API.post('/email/folders')
    },

    // History endpoints
    history: {
        getAll: (invoiceId = null) => {
            const params = invoiceId ? { invoice_id: invoiceId } : {};
            return API.get('/history', params);
        }
    },

    // PDF endpoints
    pdf: {
        view: (invoiceId) => {
            window.open(`${API.baseUrl}/pdf/${invoiceId}`, '_blank');
        }
    }
};
