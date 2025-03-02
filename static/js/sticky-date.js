document.addEventListener('DOMContentLoaded', function() {
    const stickyDate = document.getElementById('sticky-date');
    const dateSections = document.querySelectorAll('.date-section');
    let currentDateSection = null;
    let ticking = false;

    function updateStickyDate() {
        const scrollPosition = window.scrollY + 100; // Offset to account for header height
        let newCurrentSection = null;

        // Find the current date section
        dateSections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionBottom = sectionTop + section.offsetHeight;

            if (scrollPosition >= sectionTop && scrollPosition <= sectionBottom) {
                newCurrentSection = section;
            }
        });

        // Update sticky header if we have a new current section
        if (newCurrentSection && newCurrentSection !== currentDateSection) {
            currentDateSection = newCurrentSection;
            const dateStr = newCurrentSection.getAttribute('data-date');
            const date = new Date(dateStr);
            const formattedDate = date.toLocaleDateString('en-US', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
            
            document.getElementById('current-date').textContent = formattedDate;
        }

        // Show/hide sticky header based on scroll position
        if (window.scrollY > 100) {
            stickyDate.classList.add('visible');
        } else {
            stickyDate.classList.remove('visible');
        }
    }

    // Handle scroll events with requestAnimationFrame for better performance
    window.addEventListener('scroll', function() {
        if (!ticking) {
            window.requestAnimationFrame(function() {
                updateStickyDate();
                ticking = false;
            });
            ticking = true;
        }
    });

    // Initial update
    updateStickyDate();
}); 