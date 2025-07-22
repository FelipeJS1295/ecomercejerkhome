// Funciones principales de JerkHome
document.addEventListener('DOMContentLoaded', function() {
    
    // Animación suave para los enlaces
    const links = document.querySelectorAll('a[href^="#"]');
    links.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });

    // Efecto hover para las cards
    const cards = document.querySelectorAll('.card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });

    // Contador de vistas para productos (se implementará más adelante)
    function incrementarVistas(productoId) {
        fetch(`/api/producto/${productoId}/vista`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        }).catch(error => {
            console.error('Error al incrementar vistas:', error);
        });
    }

    // Función para mostrar alertas
    function mostrarAlerta(mensaje, tipo = 'success') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${tipo} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${mensaje}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        const container = document.querySelector('.container');
        if (container) {
            container.insertBefore(alertDiv, container.firstChild);
        }
    }

    // Hacer funciones globales
    window.incrementarVistas = incrementarVistas;
    window.mostrarAlerta = mostrarAlerta;
});