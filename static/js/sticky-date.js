document.addEventListener('DOMContentLoaded', function() {
    const dateHeaders = document.querySelectorAll('.date-header');
    let lastScrollTop = 0;

    window.addEventListener('scroll', function() {
        const st = window.pageYOffset || document.documentElement.scrollTop;
        
        // Add a subtle transform effect when scrolling
        dateHeaders.forEach(header => {
            const rect = header.getBoundingClientRect();
            if (rect.top === 0) {
                if (st > lastScrollTop) {
                    // Scrolling down
                    header.style.transform = 'translateY(0)';
                } else {
                    // Scrolling up
                    header.style.transform = 'translateY(0)';
                }
            }
        });
        
        lastScrollTop = st <= 0 ? 0 : st;
    }, false);
}); 