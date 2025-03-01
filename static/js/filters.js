class ConcertFilters {
    constructor() {
        this.filterPanel = document.createElement('div');
        this.filterPanel.className = 'filter-panel';
        this.preferences = {
            venues: [],
            neighborhoods: [],
            genres: []
        };
        this.setupFilterPanel();
    }

    async setupFilterPanel() {
        // Load filter options from server
        const response = await fetch('/get_filter_options');
        const data = await response.json();
        
        // Create filter sections
        this.createFilterSection('Neighborhoods', data.neighborhoods, 'neighborhoods');
        this.createFilterSection('Genres', data.genres, 'genres');
        this.createFilterSection('Venues', data.venues.map(v => v.name), 'venues');
        
        // Set initial preferences if user is logged in
        if (data.userPreferences) {
            this.preferences = data.userPreferences;
            this.updateCheckboxes();
        }
        
        // Add to page
        document.querySelector('.content-wrapper').prepend(this.filterPanel);
    }

    createFilterSection(title, options, type) {
        const section = document.createElement('div');
        section.className = 'filter-section';
        
        const heading = document.createElement('h3');
        heading.textContent = title;
        section.appendChild(heading);
        
        const optionsDiv = document.createElement('div');
        optionsDiv.className = 'filter-options';
        
        options.forEach(option => {
            const label = document.createElement('label');
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = option;
            checkbox.dataset.filterType = type;
            
            checkbox.addEventListener('change', () => this.handleFilterChange());
            
            label.appendChild(checkbox);
            label.appendChild(document.createTextNode(option));
            optionsDiv.appendChild(label);
        });
        
        section.appendChild(optionsDiv);
        this.filterPanel.appendChild(section);
    }

    async handleFilterChange() {
        // Update preferences based on checked boxes
        this.preferences = {
            venues: Array.from(document.querySelectorAll('input[data-filter-type="venues"]:checked')).map(cb => cb.value),
            neighborhoods: Array.from(document.querySelectorAll('input[data-filter-type="neighborhoods"]:checked')).map(cb => cb.value),
            genres: Array.from(document.querySelectorAll('input[data-filter-type="genres"]:checked')).map(cb => cb.value)
        };
        
        // Save preferences if user is logged in
        if (document.body.dataset.userLoggedIn === 'true') {
            await fetch('/save_preferences', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(this.preferences)
            });
        }
        
        // Update concerts display
        await this.updateConcerts();
    }

    async updateConcerts() {
        // Build query string from preferences
        const params = new URLSearchParams();
        this.preferences.venues.forEach(v => params.append('venues[]', v));
        this.preferences.neighborhoods.forEach(n => params.append('neighborhoods[]', n));
        this.preferences.genres.forEach(g => params.append('genres[]', g));
        
        // Fetch filtered concerts
        const response = await fetch(`/?${params.toString()}`, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        const data = await response.json();
        
        // Update the concerts display
        this.updateConcertsDisplay(data.concerts);
        this.updateEventCount(data.event_count);
    }

    updateCheckboxes() {
        Object.entries(this.preferences).forEach(([type, values]) => {
            const checkboxes = document.querySelectorAll(`input[data-filter-type="${type}"]`);
            checkboxes.forEach(cb => {
                cb.checked = values.includes(cb.value);
            });
        });
    }

    updateConcertsDisplay(concerts) {
        // Implementation depends on your HTML structure
        // This is a basic example
        const container = document.querySelector('.concerts-container');
        container.innerHTML = ''; // Clear existing concerts
        
        // Group concerts by date
        const concertsByDate = {};
        concerts.forEach(concert => {
            if (!concertsByDate[concert.date]) {
                concertsByDate[concert.date] = {};
            }
            if (!concertsByDate[concert.date][concert.neighborhood]) {
                concertsByDate[concert.date][concert.neighborhood] = [];
            }
            concertsByDate[concert.date][concert.neighborhood].push(concert);
        });
        
        // Render concerts
        Object.entries(concertsByDate).forEach(([date, neighborhoods]) => {
            const dateSection = this.createDateSection(date, neighborhoods);
            container.appendChild(dateSection);
        });
    }

    updateEventCount(count) {
        const countElement = document.querySelector('.event-count');
        if (countElement) {
            countElement.textContent = `${count} events found`;
        }
    }
}

// Initialize filters when page loads
document.addEventListener('DOMContentLoaded', () => {
    new ConcertFilters();
}); 