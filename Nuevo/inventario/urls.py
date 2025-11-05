# inventario/urls.py
from django.urls import path
from . import views

app_name = "inventario"

urlpatterns = [
    # Dashboard
    path("panel/", views.panel, name="panel"),
    path("panel/csv/", views.panel_csv, name="panel_csv"),

    # Materias primas y movimientos
    path("mp/", views.MPListView.as_view(), name="mp_list"),
    path("mp/nueva/", views.MPCreateView.as_view(), name="mp_create"),
    path("mp/ingreso/", views.MPIngresoView.as_view(), name="mp_ingreso"),
    path("mp/ajuste/", views.MPAjusteView.as_view(), name="mp_ajuste"),
    path("mp/merma/", views.MPMermaView.as_view(), name="mp_merma"),
    path("kardex/", views.kardex, name="kardex"),

    # Recetas
    path("recetas/", views.RecetaListView.as_view(), name="receta_list"),
    path("recetas/nueva/", views.RecetaCreateView.as_view(), name="receta_create"),
    path("recetas/<int:pk>/", views.RecetaDetailView.as_view(), name="receta_detail"),
    path("recetas/<int:pk>/editar/", views.RecetaUpdateView.as_view(), name="receta_update"),

    # Órdenes de producción
    path("op/", views.OPListView.as_view(), name="op_list"),
    path("op/nueva/", views.OPCreateView.as_view(), name="op_create"),
    path("op/<int:pk>/", views.OPDetailView.as_view(), name="op_detail"),

    # Lotes
    path("lotes/", views.LoteListView.as_view(), name="lote_list"),
    path("lotes/<int:pk>/", views.LoteDetailView.as_view(), name="lote_detail"),

    # Ventas
    path("ventas/", views.VentaListView.as_view(), name="venta_list"),
    path("ventas/nueva/", views.VentaCreateView.as_view(), name="venta_create"),
    path("ventas/<int:pk>/", views.VentaDetailView.as_view(), name="venta_detail"),
    path("predict/", views.predict_view, name="predict"),
    
    path("facturas/procesar/", views.procesar_factura, name="procesar_factura"),
    path("facturas/guardar/", views.guardar_ingreso_factura, name="guardar_ingreso_factura"),
    
    path('precios/', views.pagina_precios, name='pagina_precios'),
    
    # Esta URL recibe el nombre del plan (ej. 'plan_pro')
    path('suscribir/<str:plan_id>/', views.SimularSuscripcionView.as_view(), name='simular_suscripcion'),
    
    path('mi-suscripcion/', views.ver_suscripcion, name='ver_suscripcion'),
    # ... (tus otras urls como la de pago_exitoso/cancelado si aún las quieres)
    path('wizard/bienvenida/', views.wizard_bienvenida, name='wizard_bienvenida'),
   
    path('wizard/materias-primas/', views.wizard_materias_primas, name='wizard_materias_primas'),
    path('wizard/productos/', views.wizard_productos, name='wizard_productos'),
    path('wizard/stock-inicial/', views.wizard_stock_inicial, name='wizard_stock_inicial'),
    path('wizard/finalizar/', views.wizard_finalizar, name='wizard_finalizar'),

    # --- (Añadimos una vista simple para crear Unidades y Productos) ---
   
    path('wizard/crear-producto/', views.ProductoCreateView.as_view(), name='wizard_crear_producto'),
    path("", views.index, name="index"),
]
