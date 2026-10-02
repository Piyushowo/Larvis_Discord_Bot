// ==========================================================================
// LARVIS // CORE JS PROTOCOL
// GSAP + ScrollTrigger + Lenis Smooth Scroll
// ==========================================================================

document.addEventListener("DOMContentLoaded", () => {
    
    // --- 1. LENIS SMOOTH SCROLL INIT ---
    const lenis = new Lenis({
        duration: 1.2,
        easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
        direction: 'vertical',
        gestureDirection: 'vertical',
        smooth: true,
        mouseMultiplier: 1,
        smoothTouch: false,
        touchMultiplier: 2,
        infinite: false,
    });

    lenis.on('scroll', ScrollTrigger.update);
    gsap.ticker.add((time) => { lenis.raf(time * 1000) });
    gsap.ticker.lagSmoothing(0);

    // Remove loading lock
    document.body.classList.remove('loading');

    // --- 2. CUSTOM CURSOR & HUD COORDS ---
    const cursor = document.getElementById('custom-cursor');
    const coordDisplay = document.getElementById('mouse-coord');
    
    // Check if device supports hover
    if (window.matchMedia("(pointer: fine)").matches) {
        let mouseX = 0, mouseY = 0;
        let cursorX = 0, cursorY = 0;

        document.addEventListener('mousemove', (e) => {
            mouseX = e.clientX;
            mouseY = e.clientY;
            
            // Update HUD
            if(coordDisplay) {
                coordDisplay.innerText = `${String(mouseX).padStart(4, '0')}, ${String(mouseY).padStart(4, '0')}`;
            }
        });

        // Smooth cursor follow
        gsap.ticker.add(() => {
            cursorX += (mouseX - cursorX) * 0.2;
            cursorY += (mouseY - cursorY) * 0.2;
            gsap.set(cursor, { x: cursorX, y: cursorY });
        });

        // Hover states on interactive elements
        const interactives = document.querySelectorAll('a, button, .matrix-item, .cmd-row:not(.head)');
        interactives.forEach(el => {
            el.addEventListener('mouseenter', () => cursor.classList.add('active'));
            el.addEventListener('mouseleave', () => cursor.classList.remove('active'));
        });
    } else {
        cursor.style.display = 'none';
        document.body.style.cursor = 'auto';
    }

    // --- 3. HUD CLOCK ---
    const timeDisplay = document.getElementById('time-display');
    if(timeDisplay) {
        setInterval(() => {
            const d = new Date();
            timeDisplay.innerText = d.toISOString().substr(11, 12);
        }, 50); // Fast update for ms feel
    }

    // --- 4. SCROLL PROGRESS BAR ---
    const progressBar = document.getElementById('scroll-progress');
    if(progressBar) {
        gsap.to(progressBar, {
            height: '100%',
            ease: 'none',
            scrollTrigger: {
                trigger: document.body,
                start: 'top top',
                end: 'bottom bottom',
                scrub: 0.1
            }
        });
    }

    // --- 5. TEXT SCRAMBLE EFFECT ---
    class TextScramble {
        constructor(el) {
            this.el = el;
            this.chars = '!<>-_\\/[]{}—=+*^?#_';
            this.update = this.update.bind(this);
        }
        setText(newText) {
            const oldText = this.el.innerText;
            const length = Math.max(oldText.length, newText.length);
            const promise = new Promise((resolve) => this.resolve = resolve);
            this.queue = [];
            for (let i = 0; i < length; i++) {
                const from = oldText[i] || '';
                const to = newText[i] || '';
                const start = Math.floor(Math.random() * 40);
                const end = start + Math.floor(Math.random() * 40);
                this.queue.push({ from, to, start, end });
            }
            cancelAnimationFrame(this.frameRequest);
            this.frame = 0;
            this.update();
            return promise;
        }
        update() {
            let output = '';
            let complete = 0;
            for (let i = 0, n = this.queue.length; i < n; i++) {
                let { from, to, start, end, char } = this.queue[i];
                if (this.frame >= end) {
                    complete++;
                    output += to;
                } else if (this.frame >= start) {
                    if (!char || Math.random() < 0.28) {
                        char = this.randomChar();
                        this.queue[i].char = char;
                    }
                    output += `<span class="c-cyan">${char}</span>`;
                } else {
                    output += from;
                }
            }
            this.el.innerHTML = output;
            if (complete === this.queue.length) {
                this.resolve();
            } else {
                this.frameRequest = requestAnimationFrame(this.update);
                this.frame++;
            }
        }
        randomChar() {
            return this.chars[Math.floor(Math.random() * this.chars.length)];
        }
    }

    const scrambleEls = document.querySelectorAll('.scramble');
    scrambleEls.forEach(el => {
        const fx = new TextScramble(el);
        const originalText = el.innerText;
        
        // Trigger on intersection
        ScrollTrigger.create({
            trigger: el,
            start: "top 90%",
            onEnter: () => fx.setText(originalText)
        });

        // Trigger on hover
        el.addEventListener('mouseenter', () => {
            fx.setText(originalText);
        });
    });

    // --- 6. PARALLAX EFFECTS ---
    const parallaxImages = document.querySelectorAll('.hero-image-wrapper');
    parallaxImages.forEach(img => {
        gsap.to(img, {
            yPercent: 30,
            ease: "none",
            scrollTrigger: {
                trigger: document.body,
                start: "top top",
                end: "bottom top",
                scrub: true
            }
        });
    });

    // Matrix Grid Parallax Stagger
    const matrixItems = document.querySelectorAll('.matrix-item');
    matrixItems.forEach((item, i) => {
        const speed = parseFloat(item.dataset.speed) || 1;
        gsap.fromTo(item, 
            { y: 100 * speed },
            { 
                y: 0,
                ease: "power2.out",
                scrollTrigger: {
                    trigger: '.sec-matrix',
                    start: "top 80%",
                    end: "center center",
                    scrub: 1
                }
            }
        );

        // Animate fill bar inside matrix item
        const fill = item.querySelector('.fill');
        if(fill) {
            const targetWidth = fill.style.width;
            gsap.fromTo(fill, 
                { scaleX: 0 },
                {
                    scaleX: 1,
                    duration: 1.5,
                    ease: "expo.out",
                    scrollTrigger: {
                        trigger: item,
                        start: "top 85%"
                    }
                }
            );
        }
    });

    // --- 7. TEXT CLIPPING REVEAL ---
    const clipTexts = document.querySelectorAll('.clip-text');
    clipTexts.forEach(text => {
        gsap.fromTo(text, 
            { clipPath: "polygon(0 100%, 100% 100%, 100% 100%, 0 100%)", y: 50 },
            {
                clipPath: "polygon(0 0%, 100% 0%, 100% 100%, 0 100%)",
                y: 0,
                duration: 1.2,
                ease: "power4.out",
                scrollTrigger: {
                    trigger: text,
                    start: "top 90%"
                }
            }
        );
    });

    // --- 8. AUDIO VISUALIZER (PROCEDURAL ANIMATION) ---
    const vizContainer = document.getElementById('audio-viz');
    if (vizContainer) {
        const NUM_BARS = 40;
        const bars = [];
        for (let i = 0; i < NUM_BARS; i++) {
            const bar = document.createElement('div');
            bar.className = 'viz-bar';
            vizContainer.appendChild(bar);
            bars.push(bar);
        }

        let time = 0;
        function animateViz() {
            time += 0.05;
            bars.forEach((bar, i) => {
                // Procedural wave equation
                const noise = Math.sin(time + (i * 0.2)) * Math.cos(time * 0.8 + (i * 0.1));
                const height = Math.max(5, 50 + (noise * 40));
                bar.style.height = `${height}px`;
                // Dim edges
                const distanceFromCenter = Math.abs((NUM_BARS / 2) - i) / (NUM_BARS / 2);
                bar.style.opacity = 1 - (distanceFromCenter * 0.8);
            });
            requestAnimationFrame(animateViz);
        }
        animateViz();
    }

    // --- 9. MARQUEE CONTINUOUS ---
    const marquee = document.querySelector('.marquee-inner');
    if(marquee) {
        gsap.to(marquee, {
            xPercent: -33.33,
            ease: "none",
            duration: 10,
            repeat: -1
        });
    }
});
