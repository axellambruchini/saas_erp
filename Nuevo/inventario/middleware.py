from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch
from .models import SuscripcionCliente
import re 
from django.contrib.auth import logout

# ============================================================
# LISTA DE CAMINOS PERMITIDOS
# ============================================================
try:
    # --- URLs para usuarios CON suscripción pero EN EL WIZARD ---
    WIZARD_PATHS = [
        reverse('logout'),
        reverse('inventario:wizard_bienvenida'),
        reverse('inventario:wizard_materias_primas'),
        reverse('inventario:wizard_productos'),
        reverse('inventario:wizard_stock_inicial'),
        reverse('inventario:wizard_finalizar'),
        reverse('inventario:wizard_crear_producto'),
        reverse('inventario:mp_create'),
        reverse('inventario:mp_ingreso'),
    ]
    
    # --- URLs para usuarios SIN suscripción ---
    PRE_SUSCRIPCION_PATHS = [
        reverse('inventario:pagina_precios'),
        
        # «-- ¡AQUÍ ESTÁ LA CORRECCIÓN!
        #    Cambiamos 'home' por 'inventario:index'
        reverse('inventario:index'), 
        
        reverse('signup'),
        reverse('login'),
        reverse('logout'),
    ]

except NoReverseMatch as e:
    print(f"¡ADVERTENCIA! Error al cargar URLs del middleware: {e}")
    WIZARD_PATHS = []
    try:
        PRE_SUSCRIPCION_PATHS = [reverse('inventario:pagina_precios')]
    except NoReverseMatch:
        PRE_SUSCRIPCION_PATHS = [] # Fallback

# ============================================================
# MIDDLEWARE
# ============================================================

class SetupWizardMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. EXCLUSIONES
        if (not request.user.is_authenticated or 
            request.user.is_superuser or
            request.headers.get('x-requested-with') == 'XMLHttpRequest' or
            request.path.startswith('/media/') or 
            request.path.startswith('/static/') or
            request.path.startswith('/admin/')):
            
            return self.get_response(request)

        # 2. CHEQUEO DE SEGURIDAD
        if not hasattr(request.user, 'suscripcion'):
            logout(request)
            return redirect('login')
        
        # 3. LÓGICA PRINCIPAL
        suscripcion = request.user.suscripcion

        if suscripcion is None:
            # --- CASO 1: Usuario SIN suscripción (aún no compra) ---
            if request.path.startswith('/suscribir/'):
                return self.get_response(request)
            if request.path not in PRE_SUSCRIPCION_PATHS:
                return redirect('inventario:pagina_precios')

        else:
            # --- CASO 2: Usuario CON suscripción (ya compró) ---
            if suscripcion.ha_completado_onboarding:
                return self.get_response(request)
            if request.path not in WIZARD_PATHS:
                return redirect('inventario:wizard_bienvenida')

        return self.get_response(request)