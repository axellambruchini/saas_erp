from django.contrib import admin
from .models import (
    UnidadMedida, MateriaPrima, MovimientoMP,
    Producto, Receta, RecetaLinea, OrdenProduccion,
    LoteProducto, Venta, VentaLinea, VentaConsumo
)

# -------- Unidades / MP --------
@admin.register(UnidadMedida)
class UMAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre")
    search_fields = ("nombre",)

@admin.register(MateriaPrima)
class MPAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "unidad", "stock_minimo", "stock", "activo")
    list_filter = ("unidad", "activo")
    search_fields = ("nombre",)
    readonly_fields = ("stock",)

@admin.register(MovimientoMP)
class MovAdmin(admin.ModelAdmin):
    list_display = ("id", "mp", "tipo", "cantidad", "fecha", "nota", "created_by")
    list_filter = ("tipo", "mp")
    search_fields = ("mp__nombre", "nota")
    date_hierarchy = "fecha"

# -------- Productos / Recetas --------
class RecetaLineaInline(admin.TabularInline):
    model = RecetaLinea
    extra = 1

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "unidad", "vida_util_dias", "activo")
    list_filter = ("unidad", "activo")
    search_fields = ("nombre",)

@admin.register(Receta)
class RecetaAdmin(admin.ModelAdmin):
    list_display = ("id", "producto", "nombre", "version", "rendimiento_por_lote", "activo", "creada_en")
    list_filter = ("producto", "activo", "version")
    search_fields = ("producto__nombre", "nombre")
    inlines = [RecetaLineaInline]

# -------- Producción / Lotes --------
@admin.register(OrdenProduccion)
class OPAdmin(admin.ModelAdmin):
    list_display = ("id", "producto", "receta", "lotes", "estado", "fecha", "created_by")
    list_filter = ("estado", "producto")
    search_fields = ("id", "producto__nombre", "receta__nombre")
    date_hierarchy = "fecha"

@admin.register(LoteProducto)
class LoteAdmin(admin.ModelAdmin):
    list_display = ("codigo", "producto", "cantidad_disponible", "fecha_produccion", "fecha_vencimiento", "estado")
    list_filter = ("estado", "producto")
    search_fields = ("codigo", "producto__nombre")
    date_hierarchy = "fecha_produccion"

# -------- Ventas --------
class VentaLineaInline(admin.TabularInline):
    model = VentaLinea
    extra = 1

@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ("id", "estado", "fecha", "created_by")
    list_filter = ("estado",)
    inlines = [VentaLineaInline]
    date_hierarchy = "fecha"

@admin.register(VentaLinea)
class VentaLineaAdmin(admin.ModelAdmin):
    list_display = ("venta", "producto", "cantidad")
    search_fields = ("venta__id", "producto__nombre")

@admin.register(VentaConsumo)
class VentaConsumoAdmin(admin.ModelAdmin):
    list_display = ("venta", "linea", "lote", "cantidad", "created_at")
    list_filter = ("lote__producto",)
    date_hierarchy = "created_at"
    ordering = ("created_at",)
    search_fields = ("venta__id", "lote__codigo", "linea__producto__nombre")
