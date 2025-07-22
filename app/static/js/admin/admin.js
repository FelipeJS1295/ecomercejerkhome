// Funciones del panel de administración
document.addEventListener('DOMContentLoaded', function() {
    
    // Toggle sidebar en móviles
    const toggleSidebar = document.getElementById('toggleSidebar');
    const sidebar = document.getElementById('sidebar');
    
    if (toggleSidebar && sidebar) {
        toggleSidebar.addEventListener('click', function() {
            sidebar.classList.toggle('-translate-x-full');
        });
    }

    // Confirmación para eliminar elementos
    const deleteButtons = document.querySelectorAll('.delete-btn');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const itemName = this.getAttribute('data-name') || 'este elemento';
            
            if (confirm(`¿Estás seguro de que quieres eliminar "${itemName}"?`)) {
                // Aquí se ejecutaría la eliminación
                const url = this.getAttribute('href');
                window.location.href = url;
            }
        });
    });

    // Mostrar alerts con auto-hide
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => {
                alert.remove();
            }, 300);
        }, 5000);
    });

    // Función para previsualizar imágenes
    window.previewImage = function(input, previewId) {
        const file = input.files[0];
        const preview = document.getElementById(previewId);
        
        if (file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                preview.src = e.target.result;
                preview.classList.remove('hidden');
            };
            reader.readAsDataURL(file);
        } else {
            preview.classList.add('hidden');
        }
    };

    // Función para toggle de elementos
    window.toggleElement = function(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.classList.toggle('hidden');
        }
    };

    // Función para confirmar acciones
    window.confirmAction = function(message, callback) {
        if (confirm(message)) {
            callback();
        }
    };

    // Auto-save para formularios largos (opcional)
    const autoSaveForms = document.querySelectorAll('.auto-save');
    autoSaveForms.forEach(form => {
        const inputs = form.querySelectorAll('input, textarea, select');
        inputs.forEach(input => {
            input.addEventListener('change', function() {
                // Guardar en localStorage
                const formData = new FormData(form);
                const data = Object.fromEntries(formData);
                localStorage.setItem(`autosave_${form.id}`, JSON.stringify(data));
            });
        });
    });

    console.log('Admin panel JavaScript loaded successfully');
});

// Funciones globales para el admin
function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 px-6 py-4 rounded-lg text-white z-50 ${
        type === 'success' ? 'bg-green-500' : 
        type === 'error' ? 'bg-red-500' : 
        type === 'warning' ? 'bg-yellow-500' : 
        'bg-blue-500'
    }`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

function formatPrice(price) {
    return new Intl.NumberFormat('es-CL', {
        style: 'currency',
        currency: 'CLP'
    }).format(price);
}