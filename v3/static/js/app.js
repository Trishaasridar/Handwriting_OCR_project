/**
 * Enhanced JavaScript for Handwriting OCR Application v2
 *
 * Features:
 * - Modern AJAX with fetch API
 * - Real-time form validation
 * - Drag & drop file upload
 * - Book-style results animation
 * - Loading states and error handling
 * - Responsive design support
 */

class OCRApplication {
    constructor() {
        this.currentPage = 1;
        this.isProcessing = false;
        this.searchTimeout = null;

        this.initializeElements();
        this.bindEvents();
        this.setupFileUpload();
    }

    initializeElements() {
        // Form elements
        this.uploadForm = document.getElementById('uploadForm');
        this.studentNameInput = document.getElementById('studentName');
        this.courseNameInput = document.getElementById('courseName');
        this.fileInput = document.getElementById('handwrittenFile');
        this.uploadBtn = document.getElementById('uploadBtn');

        // Results elements
        this.resultsDisplay = document.getElementById('resultsDisplay');
        this.resultsPlaceholder = document.getElementById('resultsPlaceholder');

        // Search elements
        this.searchForm = document.getElementById('searchForm');
        this.searchStudentInput = document.getElementById('searchStudentName');
        this.searchCourseInput = document.getElementById('searchCourseName');
        this.searchBtn = document.getElementById('searchBtn');

        // Book display elements
        this.bookContainer = document.getElementById('bookContainer');
        this.leftPage = document.getElementById('leftPage');
        this.rightPage = document.getElementById('rightPage');

        // Pagination elements
        this.pagination = document.getElementById('pagination');

        // File upload area
        this.fileUploadArea = document.getElementById('fileUploadArea');
        this.fileNameDisplay = document.getElementById('fileName');
    }

    bindEvents() {
        // Form submissions
        if (this.uploadForm) {
            this.uploadForm.addEventListener('submit', (e) => this.handleUpload(e));
        }
        if (this.searchForm) {
            this.searchForm.addEventListener('submit', (e) => this.handleSearch(e));
        }

        // Real-time validation
        if (this.studentNameInput) {
            this.studentNameInput.addEventListener('input', () => this.validateForm());
        }
        if (this.courseNameInput) {
            this.courseNameInput.addEventListener('input', () => this.validateForm());
        }
        if (this.fileInput) {
            this.fileInput.addEventListener('change', () => this.handleFileSelection());
        }

        // Search input debouncing
        if (this.searchStudentInput) {
            this.searchStudentInput.addEventListener('input', () => this.debounceSearch());
        }
        if (this.searchCourseInput) {
            this.searchCourseInput.addEventListener('input', () => this.debounceSearch());
        }

        // Window resize handling
        window.addEventListener('resize', () => this.handleResize());
    }

    setupFileUpload() {
        if (!this.fileUploadArea) return;

        // Drag and drop events
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            this.fileUploadArea.addEventListener(eventName, this.preventDefaults, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            this.fileUploadArea.addEventListener(eventName, () => this.highlight(), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            this.fileUploadArea.addEventListener(eventName, () => this.unhighlight(), false);
        });

        this.fileUploadArea.addEventListener('drop', (e) => this.handleDrop(e), false);
        this.fileUploadArea.addEventListener('click', () => this.fileInput.click(), false);
    }

    // File Upload Methods
    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    highlight() {
        this.fileUploadArea.classList.add('dragover');
    }

    unhighlight() {
        this.fileUploadArea.classList.remove('dragover');
    }

    handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;

        if (files.length > 0) {
            this.fileInput.files = files;
            this.handleFileSelection();
        }
    }

    handleFileSelection() {
        const file = this.fileInput.files[0];
        if (file) {
            this.fileNameDisplay.textContent = file.name;
            this.validateForm();
        } else {
            this.fileNameDisplay.textContent = 'No file selected';
        }
    }

    validateForm() {
        const studentName = this.studentNameInput?.value.trim();
        const courseName = this.courseNameInput?.value.trim();
        const hasFile = this.fileInput?.files.length > 0;

        const isValid = studentName && courseName && hasFile && !this.isProcessing;

        if (this.uploadBtn) {
            this.uploadBtn.disabled = !isValid;
        }

        return isValid;
    }

    // Upload Handling
    async handleUpload(e) {
        e.preventDefault();

        if (!this.validateForm() || this.isProcessing) {
            return;
        }

        this.isProcessing = true;
        this.setUploadState(true);

        const formData = new FormData();
        formData.append('studentName', this.studentNameInput.value.trim());
        formData.append('courseName', this.courseNameInput.value.trim());
        formData.append('handwrittenFile', this.fileInput.files[0]);

        try {
            const response = await fetch('/api/process', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                this.showSuccess('Text extracted successfully!');
                this.displayResults(result);
                this.uploadForm.reset();
                this.fileNameDisplay.textContent = 'No file selected';
            } else {
                this.showError(result.message || 'Upload failed');
            }
        } catch (error) {
            console.error('Upload error:', error);
            this.showError('Network error occurred. Please try again.');
        } finally {
            this.isProcessing = false;
            this.setUploadState(false);
        }
    }

    setUploadState(loading) {
        if (!this.uploadBtn) return;

        if (loading) {
            this.uploadBtn.classList.add('loading');
            this.uploadBtn.textContent = 'Processing...';
            this.uploadBtn.disabled = true;
        } else {
            this.uploadBtn.classList.remove('loading');
            this.uploadBtn.textContent = 'Extract Text';
            this.uploadBtn.disabled = false;
            this.validateForm();
        }
    }

    displayResults(result) {
        if (!this.resultsDisplay) return;

        // Hide placeholder
        if (this.resultsPlaceholder) {
            this.resultsPlaceholder.style.display = 'none';
        }

        // Create result HTML
        const resultHtml = `
            <div class="result-header">
                <h3>OCR Results</h3>
                <div class="result-meta">
                    <span><strong>Student:</strong> ${result.student_name}</span>
                    <span><strong>Course:</strong> ${result.course_name}</span>
                    <span><strong>Confidence:</strong> ${(result.confidence_score * 100).toFixed(1)}%</span>
                    <span><strong>Processing Time:</strong> ${result.processing_time}s</span>
                </div>
            </div>
            <div class="result-content">
                <pre>${this.escapeHtml(result.extracted_text || 'No text extracted')}</pre>
            </div>
            <div class="result-stats">
                <span>${result.word_count} words</span>
                <span>${result.text_length} characters</span>
            </div>
        `;

        this.resultsDisplay.innerHTML = resultHtml;

        // Animate result appearance
        this.resultsDisplay.style.animation = 'none';
        setTimeout(() => {
            this.resultsDisplay.style.animation = 'fadeIn 0.5s ease';
        }, 10);
    }

    // Search Handling
    debounceSearch() {
        clearTimeout(this.searchTimeout);
        this.searchTimeout = setTimeout(() => {
            this.performSearch();
        }, 500);
    }

    async handleSearch(e) {
        if (e) e.preventDefault();
        this.performSearch();
    }

    async performSearch(page = 1) {
        const studentName = this.searchStudentInput?.value.trim();
        const courseName = this.searchCourseInput?.value.trim();

        if (!studentName && !courseName) {
            this.showError('Please enter a student name or course name');
            return;
        }

        this.currentPage = page;
        this.setSearchState(true);

        const formData = new FormData();
        formData.append('studentName', studentName);
        formData.append('courseName', courseName);
        formData.append('page', page.toString());

        try {
            const response = await fetch('/api/search', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                this.displaySearchResults(result);
            } else {
                this.showError(result.message || 'Search failed');
                this.clearBookDisplay();
            }
        } catch (error) {
            console.error('Search error:', error);
            this.showError('Network error occurred during search');
            this.clearBookDisplay();
        } finally {
            this.setSearchState(false);
        }
    }

    setSearchState(loading) {
        if (!this.searchBtn) return;

        if (loading) {
            this.searchBtn.disabled = true;
            this.searchBtn.innerHTML = '<div class="spinner"></div> Searching...';
        } else {
            this.searchBtn.disabled = false;
            this.searchBtn.textContent = 'Search';
        }
    }

    displaySearchResults(result) {
        if (!result.records || result.records.length === 0) {
            this.clearBookDisplay();
            this.showInfo('No records found');
            return;
        }

        this.renderBookPages(result.records);
        this.renderPagination(result);
        this.animateBookFlip();
    }

    renderBookPages(records) {
        const leftRecords = records.slice(0, 4);
        const rightRecords = records.slice(4, 8);

        // Render left page
        if (this.leftPage) {
            this.leftPage.innerHTML = leftRecords.map(record =>
                this.createResultCard(record)
            ).join('');
        }

        // Render right page
        if (this.rightPage) {
            this.rightPage.innerHTML = rightRecords.map(record =>
                this.createResultCard(record)
            ).join('');
        }
    }

    createResultCard(record) {
        const confidence = record.confidence_score || 0;
        const confidenceClass = confidence > 0.8 ? 'high' :
                               confidence > 0.6 ? 'medium' : 'low';
        const confidencePercent = (confidence * 100).toFixed(1);

        return `
            <div class="result-card">
                <div class="result-meta">
                    <span><strong>${record.student_name}</strong> - ${record.course_name}</span>
                    <span class="confidence-badge ${confidenceClass}">${confidencePercent}%</span>
                </div>
                <div class="result-text">${this.escapeHtml(record.content || 'No content')}</div>
                ${record.image ? `<img src="data:image/jpeg;base64,${record.image}" alt="Handwritten text" class="result-image">` : ''}
                <div class="result-date">${record.date} ${record.time}</div>
            </div>
        `;
    }

    renderPagination(result) {
        if (!this.pagination) return;

        const { page, total_pages, total_records } = result;
        let paginationHtml = '';

        if (total_pages > 1) {
            // Previous button
            if (page > 1) {
                paginationHtml += `<button class="page-btn" onclick="app.performSearch(${page - 1})">‹ Previous</button>`;
            }

            // Page numbers
            const startPage = Math.max(1, page - 2);
            const endPage = Math.min(total_pages, page + 2);

            for (let i = startPage; i <= endPage; i++) {
                const activeClass = i === page ? ' active' : '';
                paginationHtml += `<button class="page-btn${activeClass}" onclick="app.performSearch(${i})">${i}</button>`;
            }

            // Next button
            if (page < total_pages) {
                paginationHtml += `<button class="page-btn" onclick="app.performSearch(${page + 1})">Next ›</button>`;
            }
        }

        this.pagination.innerHTML = paginationHtml || '<div class="no-results">No pagination needed</div>';
    }

    animateBookFlip() {
        if (!this.bookContainer) return;

        // Add flip animation
        this.bookContainer.style.animation = 'none';
        setTimeout(() => {
            this.bookContainer.style.animation = 'bookFlip 0.8s ease';
        }, 10);
    }

    clearBookDisplay() {
        if (this.leftPage) this.leftPage.innerHTML = '';
        if (this.rightPage) this.rightPage.innerHTML = '';
        if (this.pagination) this.pagination.innerHTML = '';
    }

    // Utility Methods
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showSuccess(message) {
        this.showMessage(message, 'success');
    }

    showError(message) {
        this.showMessage(message, 'error');
    }

    showWarning(message) {
        this.showMessage(message, 'warning');
    }

    showInfo(message) {
        this.showMessage(message, 'info');
    }

    showMessage(message, type) {
        // Remove existing messages
        const existingMessages = document.querySelectorAll('.status-message');
        existingMessages.forEach(msg => msg.remove());

        // Create new message
        const messageDiv = document.createElement('div');
        messageDiv.className = `status-message ${type}`;
        messageDiv.innerHTML = `
            <i class="fas fa-${this.getIconForType(type)}"></i>
            <span>${message}</span>
        `;

        // Insert at top of container
        const container = document.querySelector('.container');
        if (container) {
            container.insertBefore(messageDiv, container.firstChild);
        }

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, 5000);
    }

    getIconForType(type) {
        const icons = {
            success: 'check-circle',
            error: 'exclamation-circle',
            warning: 'exclamation-triangle',
            info: 'info-circle'
        };
        return icons[type] || 'info-circle';
    }

    handleResize() {
        // Handle responsive design changes
        const isMobile = window.innerWidth <= 768;

        if (isMobile && this.rightPage) {
            // On mobile, hide right page
            this.rightPage.style.display = 'none';
        } else if (this.rightPage) {
            this.rightPage.style.display = 'block';
        }
    }
}

// Initialize application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new OCRApplication();
});

// Global error handler
window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
    if (window.app) {
        window.app.showError('An unexpected error occurred. Please refresh the page.');
    }
});

window.addEventListener('error', (event) => {
    console.error('JavaScript error:', event.error);
    if (window.app) {
        window.app.showError('A JavaScript error occurred. Please refresh the page.');
    }
});